from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass


def _preview_output(output: str, head: int = 5, tail: int = 5, max_col: int = 100) -> str:
    if not output:
        return ""
    lines = [l[:max_col] for l in output.splitlines()]
    if len(lines) <= head + tail:
        return "\n".join(lines)
    omitted = len(lines) - head - tail
    return "\n".join(lines[:head]) + f"\n... ({omitted} 行省略) ...\n" + "\n".join(lines[-tail:])


@dataclass
class ListBackgroundShellExecutionsTool(FunctionTool[AstrAgentContext]):
    name: str = "list_background_shell_executions"
    description: str = "列出所有通过 execute_shell 工具后台运行的任务及其状态，并显示每个任务的部分输出预览。"
    parameters: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})

    task_mgr: object = None

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        tasks = self.task_mgr.list_tasks()
        if not tasks:
            return "当前没有后台任务"
        parts = []
        for tid, t in tasks.items():
            header = f"[{tid}] {t.status} - {t.description or t.command[:40]}"
            output = t.current_output() if t.status == "running" else (t.result or "")
            preview = _preview_output(output)
            parts.append(header + ("\n" + preview if preview else ""))
        return "\n\n".join(parts)
