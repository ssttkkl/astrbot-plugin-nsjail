import asyncio
import platform

from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass

from ..sandbox_config import SandboxConfig
from ..background_tasks import BackgroundTaskManager


def get_tool_prompt(config: SandboxConfig) -> str:
    perm_desc = {
        "all": "所有用户可读写",
        "admin": "仅管理员可写，其他用户只读",
        "none": "只读",
    }
    data_perm = perm_desc.get(config.data_write_permission, "只读")
    skills_perm = perm_desc.get(config.skills_write_permission, "只读")
    bg_section = ""
    if config.enable_background:
        bg_section = f"""
后台执行模式（background=true）：
- 适用场景：预计耗时较长（>10秒）、编译/下载/训练等任务、用户无需等待的操作
- 不适用：需要立即返回结果、交互式命令、简单查询
- 最大超时：{config.background_max_timeout}秒
- 任务完成后会自动将结果发送到当前会话，无需轮询
- 必须提供 description 参数简短描述任务目的
"""
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
- 网络访问：{network}{bg_section}"""


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
    task_mgr: object = None

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
            task_id = self.task_mgr.create_task(self.sandbox_mgr, astrbot_context, event, session_id, command, timeout, is_admin, kwargs.get("description", ""))
            return f"命令已在后台运行，任务ID: {task_id}，完成后将自动发送结果到会话。"

        timeout = min(kwargs.get("timeout", self.timeout_seconds), self.timeout_seconds)
        execution = await self.sandbox_mgr.start_execution(session_id, command, timeout, is_admin)
        try:
            await execution.wait(timeout=None if timeout == -1 else timeout + 5)
        except asyncio.TimeoutError:
            pass
        output = execution.get_stdout() + execution.get_stderr()
        code = execution.returncode if execution.returncode is not None else -1
        prefix = "执行超时，当前输出" if execution.returncode is None else f"退出码: {code}"
        return f"$ {command}\n{output}\n{prefix}"
