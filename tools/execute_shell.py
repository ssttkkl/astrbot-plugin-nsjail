import asyncio
from astrbot.api import FunctionTool
from astrbot.api.event import AstrMessageEvent
from dataclasses import dataclass, field

@dataclass
class ExecuteShellTool(FunctionTool):
    name: str = "execute_shell"
    description: str = "在隔离的沙箱环境中执行 shell 命令。每个会话有独立的沙箱,文件系统隔离,资源受限。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令",
                },
                "timeout": {
                    "type": "number",
                    "description": "超时时间(秒),默认30秒",
                },
            },
            "required": ["command"],
        }
    )
    
    plugin_instance: any = None

    async def run(self, event: AstrMessageEvent, command: str, timeout: int = 30):
        if not self.plugin_instance:
            return "插件未正确初始化"

        session_id = event.session_id or "default"
        output, code = await self.plugin_instance.execute_in_sandbox(session_id, command, timeout)
        return f"$ {command}\n{output}\n退出码: {code}"
