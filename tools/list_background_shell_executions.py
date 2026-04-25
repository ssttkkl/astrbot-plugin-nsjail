from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass

from ..background_tasks import BackgroundTaskManager


@dataclass
class ListBackgroundShellExecutionsTool(FunctionTool[AstrAgentContext]):
    name: str = "list_background_shell_executions"
    description: str = "列出所有正在运行的后台任务及其状态。"
    parameters: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})

    task_mgr: object = None

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        tasks = self.task_mgr.list_tasks()
        if not tasks:
            return "当前没有后台任务"
        lines = [f"[{tid}] {t['status']} - {t['description'] or t['command'][:40]}" for tid, t in tasks.items()]
        return "\n".join(lines)
