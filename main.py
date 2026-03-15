import asyncio
import re
import os
from pathlib import Path
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
import astrbot.api.message_components as Comp
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from pydantic import Field
from pydantic.dataclasses import dataclass
from .sandbox_manager import SandboxManager
from .sandbox_config import SandboxConfig


@dataclass
class ExecuteShellTool(FunctionTool[AstrAgentContext]):
    name: str = "execute_shell"
    description: str = ""
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "timeout": {
                    "type": "number",
                    "description": "超时时间(秒)，默认30秒",
                },
            },
            "required": ["command"],
        }
    )
    sandbox_mgr: object = None
    
    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 30)
        
        event = context.context.event
        session_id = event.session_id or "default"
        is_admin = event.role == "admin"
        
        output, code = await self.sandbox_mgr.execute_in_sandbox(session_id, command, timeout, is_admin)
        return f"$ {command}\n{output}\n退出码: {code}"


class NsjailPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        max_timeout = config.get("max_timeout", 60)
        enable_network = config.get("enable_network", False)
        memory_limit_mb = config.get("memory_limit_mb", -1)
        cpu_limit_percent = config.get("cpu_limit_percent", -1)
        cpu_cores_limit = config.get("cpu_cores_limit", -1)
        process_limit = config.get("process_limit", 50)
        data_write_permission = config.get("data_write_permission", "none")
        skills_write_permission = config.get("skills_write_permission", "none")
        custom_mounts = config.get("custom_mounts", [])
        sandbox_symlinks = config.get("sandbox_symlinks", [])
        path = config.get("path", None)
        custom_env = config.get("custom_env", [])
        extra_path = config.get("extra_path", [])
        custom_env = config.get("custom_env", [])
        
        plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_nsjail"
        plugin_data_path.mkdir(parents=True, exist_ok=True)
        
        # 检查 Cgroup V2 是否可用
        cgroup_available = False
        try:
            test_cgroup = "/sys/fs/cgroup/nsjail_test"
            os.makedirs(test_cgroup, exist_ok=True)
            # 尝试写入 cgroup.procs（这是 nsjail 真正需要的操作）
            with open(f"{test_cgroup}/cgroup.procs", "w") as f:
                f.write(str(os.getpid()))
            os.rmdir(test_cgroup)
            cgroup_available = True
            logger.info("Cgroup V2 可用，将启用内存和 CPU 限制")
        except Exception as e:
            logger.warning(f"Cgroup V2 不可用，将跳过内存和 CPU 使用率限制: {e}")
        
        sandbox_config = SandboxConfig(
            data_dir=str(plugin_data_path),
            max_timeout=max_timeout,
            enable_network=enable_network,
            memory_limit_mb=memory_limit_mb if cgroup_available else -1,
            cpu_limit_percent=cpu_limit_percent if cgroup_available else -1,
            cpu_cores_limit=cpu_cores_limit,
            process_limit=process_limit,
            data_write_permission=data_write_permission,
            skills_write_permission=skills_write_permission,
            custom_mounts=custom_mounts,
            sandbox_symlinks=sandbox_symlinks,
            path=path,
            custom_env=custom_env,
            cgroup_available=cgroup_available
        )
        
        self.sandbox_mgr = SandboxManager(sandbox_config)
        
        # 启动时清理所有沙箱目录
        self.sandbox_mgr.cleanup_all_sandboxes()
        
        # 动态生成权限描述
        data_perm_desc = {
            "all": "所有用户可读写",
            "admin": "仅管理员可写，其他用户只读",
            "none": "只读"
        }.get(data_write_permission, "只读")
        
        skills_perm_desc = {
            "all": "所有用户可读写",
            "admin": "仅管理员可写，其他用户只读",
            "none": "只读"
        }.get(skills_write_permission, "只读")
        
        network_desc = "已启用" if enable_network else "已禁用"
        
        # 生成资源限制描述
        memory_desc = f"{memory_limit_mb}MB" if memory_limit_mb > 0 else "无限制"
        cpu_desc = f"{cpu_limit_percent}%" if cpu_limit_percent > 0 else "无限制"
        cpu_cores_desc = f"{cpu_cores_limit}核" if cpu_cores_limit > 0 else "无限制"
        
        # 获取实际的 skills 目录路径
        skills_dir_path = sandbox_config.skills_dir
        
        tool_description = f"""在隔离的沙箱环境中执行 shell 命令。

🚨 上下文限制（必读）：
每次调用都是独立的新进程，不保留任何状态：
- ❌ 环境变量不保留：export MY_VAR=value 在下次调用时丢失
- ❌ 工作目录不保留：cd /some/dir 在下次调用时回到 /workspace
- ✅ 文件会保留：写入 /workspace 的文件在会话内持久化

正确的多步骤写法：
- ✅ cd /workspace/subdir && python script.py
- ✅ export VAR=value && echo $VAR
- ❌ 第一次调用 cd /workspace/subdir，第二次调用 python script.py

沙箱目录结构：
- /workspace: 当前会话的工作目录（可读写），命令默认在此执行
- /data: 共享数据目录，用于跨会话持久化数据（当前权限：{data_perm_desc}）
  * 每个技能的持久化文件（数据、密钥、缓存等）应放在 /data/<技能名>/ 子目录下
  * 例如：/data/weather/cache.json, /data/github/token.txt
- {skills_dir_path}: 技能目录，可调用已安装的技能脚本（当前权限：{skills_perm_desc}）
- ~/.agents/skills: 符号链接到 {skills_dir_path}
- /usr, /bin, /lib: 系统工具和库（只读），包含 Python、Node.js、Git 等
- /tmp: 临时文件目录（可读写）

资源限制：
- 内存限制：{memory_desc}
- CPU 使用率：{cpu_desc}
- CPU 核数：{cpu_cores_desc}
- 网络访问：{network_desc}"""
        
        # 注册动态 Tool
        execute_shell_tool = ExecuteShellTool(
            description=tool_description,
            sandbox_mgr=self.sandbox_mgr
        )
        self.context.add_llm_tools(execute_shell_tool)
    
    @filter.llm_tool(name="send_sandbox_image")
    async def send_sandbox_image(self, event: AstrMessageEvent, image_path: str):
        """
        发送沙箱内的图片到当前会话。图片必须是通过 execute_shell 工具执行命令后产出到沙箱的。
        
        Args:
            image_path(string): 沙箱内的图片路径（相对于 /workspace 或 /tmp 或绝对路径）
        """
        session_id = event.session_id or "default"
        
        real_path = self.sandbox_mgr.resolve_sandbox_path(session_id, image_path)
        if not real_path:
            yield event.plain_result("错误: 沙箱未初始化")
            return
        
        if not os.path.exists(real_path):
            yield event.plain_result(f"错误: 图片文件不存在: {image_path}")
            return
        
        yield event.image_result(real_path)
    
    @filter.llm_tool(name="send_sandbox_file")
    async def send_sandbox_file(self, event: AstrMessageEvent, file_path: str):
        """
        发送沙箱内的文件到当前会话。文件必须是通过 execute_shell 工具执行命令后产出到沙箱的。
        
        Args:
            file_path(string): 沙箱内的文件路径（相对于 /workspace 或 /tmp 或绝对路径）
        """
        session_id = event.session_id or "default"
        
        real_path = self.sandbox_mgr.resolve_sandbox_path(session_id, file_path)
        if not real_path:
            yield event.plain_result("错误: 沙箱未初始化")
            return
        
        if not os.path.exists(real_path):
            yield event.plain_result(f"错误: 文件不存在: {file_path}")
            return
        
        file_name = os.path.basename(real_path)
        yield event.chain_result([Comp.File(file=real_path, name=file_name)])
    
    @filter.command("nsjail")
    async def handle_nsjail_command(self, event: AstrMessageEvent):
        """处理 /nsjail 命令"""
        # 移除 /nsjail 前缀和可能的空格
        full_msg = event.message_str.strip()
        if full_msg.startswith('/nsjail'):
            command = full_msg[7:].strip()
        elif full_msg.startswith('nsjail'):
            command = full_msg[6:].strip()
        else:
            command = full_msg
        
        if not command:
            yield event.plain_result("用法: /nsjail <命令>")
            return
        
        if len(command) > 1000:
            yield event.plain_result("命令过长（最大 1000 字符）")
            return
        
        session_id = event.session_id or "default"
        is_admin = event.role == "admin"
        output, returncode = await self.sandbox_mgr.execute_in_sandbox(session_id, command, is_admin=is_admin)
        
        response = f"退出码: {returncode}\n输出:\n{output}"
        yield event.plain_result(response[:2000])
    
    @filter.command("nsjail-clean")
    async def handle_clean_command(self, event: AstrMessageEvent):
        """清理当前会话的沙箱目录"""
        session_id = event.session_id or "default"
        
        if session_id in self.sandbox_mgr.sandboxes:
            self.sandbox_mgr.destroy_sandbox(session_id)
            yield event.plain_result(f"✅ 已清理会话 {session_id} 的沙箱目录")
        else:
            yield event.plain_result(f"⚠️ 会话 {session_id} 没有沙箱目录")
    
    async def terminate(self):
        for session_id in list(self.sandbox_mgr.sandboxes.keys()):
            self.sandbox_mgr.destroy_sandbox(session_id)
