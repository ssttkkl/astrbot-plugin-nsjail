from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass

from ..background_tasks import BackgroundTaskManager


@dataclass
class CancelBackgroundShellExecutionTool(FunctionTool[AstrAgentContext]):
    name: str = "cancel_background_shell_execution"
    description: str = "立即终止一个正在后台运行的 shell 任务。"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "后台任务ID，由 execute_shell 的 background 模式返回"},
        },
        "required": ["task_id"],
    })

    task_mgr: object = None

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        task_id = kwargs.get("task_id", "")
        if self.task_mgr.cancel_task(task_id):
            return f"任务 {task_id} 已终止"
        return f"任务 {task_id} 不存在或已完成"
