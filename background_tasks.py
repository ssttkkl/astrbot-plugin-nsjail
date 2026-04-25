import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sandbox_manager import Execution

from astrbot.core.astr_main_agent_resources import (
    BACKGROUND_TASK_RESULT_WOKE_SYSTEM_PROMPT,
    SEND_MESSAGE_TO_USER_TOOL,
)
from astrbot.core.cron.events import CronMessageEvent
from astrbot.core.platform.astr_message_event import MessageSession
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.agent.tool import ToolSet


@dataclass
class BackgroundTask:
    command: str
    description: str = ""
    status: str = "running"
    result: Optional[str] = None
    asyncio_task: Optional[asyncio.Task] = field(default=None, repr=False)
    execution: Optional["Execution"] = field(default=None, repr=False)

    def current_output(self) -> str:
        if self.execution and self.status == "running":
            return self.execution.get_stdout() + self.execution.get_stderr()
        return ""


class BackgroundTaskManager:
    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}

    def create_task(self, execution: "Execution", astrbot_context, event, command: str, description: str = "") -> str:
        task_id = str(uuid.uuid4())[:8]
        task = BackgroundTask(command=command, description=description, execution=execution)
        self._tasks[task_id] = task
        task.asyncio_task = asyncio.create_task(self._run(task_id, astrbot_context, event, command))
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status != "running":
            return False
        if task.asyncio_task:
            task.asyncio_task.cancel()
        self._tasks.pop(task_id, None)
        return True

    def query_task(self, task_id: str) -> Optional[BackgroundTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> dict[str, BackgroundTask]:
        return dict(self._tasks)

    async def _run(self, task_id, astrbot_context, event, command):
        from astrbot.core.astr_main_agent import MainAgentBuildConfig, _get_session_conv, build_main_agent

        task = self._tasks[task_id]
        desc_line = f" ({task.description})" if task.description else ""
        try:
            await task.execution.wait()
            output = task.execution.get_stdout() + task.execution.get_stderr()
            result = f"$ {command}\n{output}\n{'执行超时' if task.execution.timed_out else f'退出码: {task.execution.returncode}'}"
            task.status = "done"
            task.result = result
            note = f"[后台任务完成] ID: {task_id}{desc_line}\n{result}"
        except Exception as e:
            result = str(e)
            task.status = "error"
            task.result = result
            note = f"[后台任务失败] ID: {task_id}{desc_line}\n$ {command}\n{e}"
        finally:
            self._tasks.pop(task_id, None)

        task_result = {"task_id": task_id, "tool_name": "execute_shell", "result": result, "tool_args": {"command": command}}
        session = MessageSession.from_str(event.unified_msg_origin)
        cron_event = CronMessageEvent(
            context=astrbot_context,
            session=session,
            message=note,
            extras={"background_task_result": task_result},
            message_type=session.message_type,
        )
        cron_event.role = event.role

        config = MainAgentBuildConfig(
            tool_call_timeout=3600,
            streaming_response=astrbot_context.get_config().get("provider_settings", {}).get("stream", False),
        )
        req = ProviderRequest()
        conv = await _get_session_conv(event=cron_event, plugin_context=astrbot_context)
        req.conversation = conv
        context = json.loads(conv.history)
        if context:
            req.contexts = context
            context_dump = req._print_friendly_context()
            req.contexts = []
            req.system_prompt += "\n\nBellow is you and user previous conversation history:\n" + context_dump

        req.system_prompt += BACKGROUND_TASK_RESULT_WOKE_SYSTEM_PROMPT.format(
            background_task_result=json.dumps(task_result, ensure_ascii=False)
        )
        req.prompt = (
            "Proceed according to your system instructions. "
            "Output using same language as previous conversation. "
            "If you need to deliver the result to the user immediately, "
            "you MUST use `send_message_to_user` tool to send the message directly to the user, "
            "otherwise the user will not see the result. "
            "After completing your task, summarize and output your actions and results. "
        )
        if not req.func_tool:
            req.func_tool = ToolSet()
        req.func_tool.add_tool(SEND_MESSAGE_TO_USER_TOOL)

        result_obj = await build_main_agent(event=cron_event, plugin_context=astrbot_context, config=config, req=req)
        if not result_obj:
            return
        async for _ in result_obj.agent_runner.step_until_done(30):
            pass
