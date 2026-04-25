import asyncio
import os
import platform
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import ProviderRequest
import astrbot.api.message_components as Comp
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.api.star import StarTools
from pydantic import Field
from pydantic.dataclasses import dataclass
from .sandbox_manager import SandboxManager
from .sandbox_config import SandboxConfig
from . import background_tasks


@dataclass
class ExecuteShellTool(FunctionTool[AstrAgentContext]):
    name: str = "execute_shell"
    description: str = ""
    timeout_seconds: int = 60
    background_timeout_seconds: int = 600
    enable_background: bool = True
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {"type": "number", "description": "超时时间(秒)"},
        },
        "required": ["command"],
    })
    sandbox_mgr: object = None

    def __post_init__(self):
        if self.enable_background:
            self.parameters["properties"]["background"] = {"type": "boolean", "description": "是否在后台运行，完成后自动将结果发送到会话"}
            self.parameters["properties"]["description"] = {"type": "string", "description": "后台任务的简短描述（后台模式必填），用于后续识别"}

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        command = kwargs.get("command", "")
        if len(command) > 65535:
            return "命令过长（最大 65535 字符）"

        event = context.context.event
        session_id = event.session_id or "default"
        is_admin = event.is_admin()

        if kwargs.get("background"):
            if not self.enable_background:
                return "后台模式未启用"
            timeout = min(kwargs.get("timeout", self.background_timeout_seconds), self.background_timeout_seconds)
            astrbot_context = context.context.context
            task_id = background_tasks.create_task(self.sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, event.unified_msg_origin, kwargs.get("description", ""))
            return f"命令已在后台运行，任务ID: {task_id}，完成后将自动发送结果到会话。"

        timeout = min(kwargs.get("timeout", self.timeout_seconds), self.timeout_seconds)
        output, code = await self.sandbox_mgr.execute_in_sandbox(session_id, command, timeout, is_admin)
        return f"$ {command}\n{output}\n退出码: {code}"


def get_tool_prompt(config: SandboxConfig) -> str:
    perm_desc = {
        "all": "所有用户可读写",
        "admin": "仅管理员可写，其他用户只读",
        "none": "只读",
    }
    data_perm = perm_desc.get(config.data_write_permission, "只读")
    skills_perm = perm_desc.get(config.skills_write_permission, "只读")
    network = "已启用" if config.enable_network else "已禁用"
    memory = f"{config.memory_limit_mb}MB" if config.memory_limit_mb > 0 else "无限制"
    cpu = f"{config.cpu_limit_percent}%" if config.cpu_limit_percent > 0 else "无限制"
    cpu_cores = f"{config.cpu_cores_limit}核" if config.cpu_cores_limit > 0 else "无限制"

    uname = platform.uname()
    sys_info = f"{uname.system} {uname.release} ({uname.machine})"

    return f"""在隔离的沙箱环境中执行 shell 命令。

宿主系统：{sys_info}

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
- /data: 共享数据目录，用于跨会话持久化数据（当前权限：{data_perm}）
  * 每个技能的持久化文件（数据、密钥、缓存等）应放在 /data/<技能名>/ 子目录下
  * 例如：/data/weather/cache.json, /data/github/token.txt
- {config.skills_dir}: 技能目录，可调用已安装的技能脚本（当前权限：{skills_perm}）
- /usr, /bin, /lib: 系统工具和库（只读），包含 Python、Node.js、Git 等
- /tmp: 临时文件目录（可读写）

资源限制：
- 内存限制：{memory}
- CPU 使用率：{cpu}
- CPU 核数：{cpu_cores}
- 网络访问：{network}"""


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
        
        # 过滤掉模板键
        sandbox_symlinks = [
            {k: v for k, v in item.items() if not k.startswith("__")}
            for item in sandbox_symlinks
            if isinstance(item, dict)
        ]
        
        path = config.get("path", None)
        custom_env = config.get("custom_env", [])
        enable_background = config.get("enable_background", True)
        background_max_timeout = config.get("background_max_timeout", 600)
        plugin_data_path = StarTools.get_data_dir()
        plugin_data_path.mkdir(parents=True, exist_ok=True)

        sandbox_config = SandboxConfig(
            data_dir=str(plugin_data_path),
            max_timeout=max_timeout,
            enable_network=enable_network,
            memory_limit_mb=memory_limit_mb,
            cpu_limit_percent=cpu_limit_percent,
            cpu_cores_limit=cpu_cores_limit,
            process_limit=process_limit,
            data_write_permission=data_write_permission,
            skills_write_permission=skills_write_permission,
            custom_mounts=custom_mounts,
            sandbox_symlinks=sandbox_symlinks,
            path=path,
            custom_env=custom_env,
            enable_background=enable_background,
            background_max_timeout=background_max_timeout,
        )

        self.sandbox_mgr = SandboxManager(sandbox_config)

        execute_shell_tool = ExecuteShellTool(
            description=get_tool_prompt(sandbox_config),
            timeout_seconds=max_timeout,
            background_timeout_seconds=background_max_timeout,
            enable_background=enable_background,
            sandbox_mgr=self.sandbox_mgr,
        )
        self.context.add_llm_tools(execute_shell_tool)

    @filter.llm_tool(name="query_background_task")
    async def query_background_task(self, event: AstrMessageEvent, task_id: str):
        """
        查询后台任务的执行状态和结果。

        Args:
            task_id(string): 后台任务ID，由 execute_shell 的 background 模式返回
        """
        task = background_tasks.query_task(task_id)
        if not task:
            yield event.plain_result(f"任务 {task_id} 不存在")
            return
        status = task["status"]
        if status == "running":
            yield event.plain_result(f"任务 {task_id} 正在运行中...")
        else:
            yield event.plain_result(f"[任务{task_id}] 状态: {status}\n{task['result']}")

    _COMPUTER_USE_NOTICE = "User has not enabled the Computer Use feature. You cannot use shell or Python to perform skills. If you need to use these capabilities, ask the user to enable Computer Use in the AstrBot WebUI -> Config.\n"

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, request: ProviderRequest) -> None:
        request.system_prompt = request.system_prompt.replace(self._COMPUTER_USE_NOTICE, "")

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
            yield event.plain_result("错误: 无法解析文件路径")
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
            yield event.plain_result("错误: 无法解析文件路径")
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
        
        if len(command) > 65535:
            yield event.plain_result("命令过长（最大 65535 字符）")
            return
        
        session_id = event.session_id or "default"
        is_admin = event.is_admin()
        output, returncode = await self.sandbox_mgr.execute_in_sandbox(session_id, command, timeout=self.sandbox_mgr.config.max_timeout, is_admin=is_admin)
        
        response = f"退出码: {returncode}\n输出:\n{output}"
        if len(response) > 2000:
            head = response[:1000]
            tail = response[-900:]
            response = head + "\n...[内容已截断]...\n" + tail
        yield event.plain_result(response)
    
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
