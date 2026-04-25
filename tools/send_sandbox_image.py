import os

from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass


@dataclass
class SendSandboxImageTool(FunctionTool[AstrAgentContext]):
    name: str = "send_sandbox_image"
    description: str = "发送沙箱内的图片到当前会话。图片必须是通过 execute_shell 工具执行命令后产出到沙箱的。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "沙箱内的图片路径（相对于 /workspace 或 /tmp 或绝对路径）"},
        },
        "required": ["image_path"],
    })
    sandbox_mgr: object = None

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        from astrbot.api.event import MessageChain
        import astrbot.api.message_components as Comp

        image_path = kwargs.get("image_path", "")
        event = context.context.event
        session_id = event.session_id or "default"

        real_path = self.sandbox_mgr.resolve_sandbox_path(session_id, image_path)
        if not real_path:
            return "错误: 无法解析文件路径"
        if not os.path.exists(real_path):
            return f"错误: 图片文件不存在: {image_path}"

        astrbot_context = context.context.context
        await astrbot_context.send_message(
            event.unified_msg_origin,
            MessageChain().chain([Comp.Image(file=real_path)])
        )
        return "图片已发送"
