import os

from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass


@dataclass
class SendSandboxFileTool(FunctionTool[AstrAgentContext]):
    name: str = "send_sandbox_file"
    description: str = "发送沙箱内的文件到当前会话。文件必须是通过 execute_shell 工具执行命令后产出到沙箱的。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "沙箱内的文件路径（相对于 /workspace 或 /tmp 或绝对路径）"},
        },
        "required": ["file_path"],
    })
    sandbox_mgr: object = None

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from astrbot.api.event import MessageChain
        import astrbot.api.message_components as Comp

        file_path = kwargs.get("file_path", "")
        event = context.context.event
        session_id = event.session_id or "default"

        real_path = self.sandbox_mgr.resolve_sandbox_path(session_id, file_path)
        if not real_path:
            return "错误: 无法解析文件路径"
        if not os.path.exists(real_path):
            return f"错误: 文件不存在: {file_path}"

        file_name = os.path.basename(real_path)
        astrbot_context = context.context.context
        await astrbot_context.send_message(
            event.unified_msg_origin,
            MessageChain().chain([Comp.File(file=real_path, name=file_name)])
        )
        return "文件已发送"
