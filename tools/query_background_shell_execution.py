from astrbot.api.event import AstrMessageEvent
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass

from ..background_tasks import BackgroundTaskManager


@dataclass
class QueryBackgroundShellExecutionTool(FunctionTool[AstrAgentContext]):
    name: str = "query_background_shell_execution"
    description: str = "查询后台任务的执行状态和结果。"
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
        task = self.task_mgr.query_task(task_id)
        if not task:
            return f"任务 {task_id} 不存在"
        if task.status == "running":
            current = task.current_output()
            return f"任务 {task_id} 正在运行中...\n当前输出:\n{current}" if current else f"任务 {task_id} 正在运行中..."
        return f"[任务{task_id}] 状态: {task.status}\n{task.result}"
