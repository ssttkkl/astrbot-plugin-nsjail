import asyncio
import json
import uuid

from astrbot.core.astr_main_agent_resources import (
    BACKGROUND_TASK_RESULT_WOKE_SYSTEM_PROMPT,
    SEND_MESSAGE_TO_USER_TOOL,
)
from astrbot.core.cron.events import CronMessageEvent
from astrbot.core.platform.astr_message_event import MessageSession
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.agent.tool import ToolSet


class BackgroundTaskManager:
    def __init__(self):
        self._tasks: dict = {}

    def create_task(self, sandbox_mgr, astrbot_context, event, session_id, command, timeout, is_admin, description: str = "") -> str:
        task_id = str(uuid.uuid4())[:8]
        self._tasks[task_id] = {"status": "running", "command": command, "description": description, "result": None, "asyncio_task": None, "execution": None}
        t = asyncio.create_task(self._run(task_id, sandbox_mgr, astrbot_context, event, session_id, command, timeout, is_admin))
        self._tasks[task_id]["asyncio_task"] = t
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task["status"] != "running":
            return False
        t = task.get("asyncio_task")
        if t:
            t.cancel()
        self._tasks.pop(task_id, None)
        return True

    def query_task(self, task_id: str) -> dict | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        result = dict(task)
        execution = task.get("execution")
        if execution and task["status"] == "running":
            result["current_output"] = execution.get_stdout() + execution.get_stderr()
        return result

    def list_tasks(self) -> dict:
        return dict(self._tasks)

    async def _run(self, task_id, sandbox_mgr, astrbot_context, event, session_id, command, timeout, is_admin):
        from astrbot.core.astr_main_agent import MainAgentBuildConfig, _get_session_conv, build_main_agent

        description = self._tasks[task_id]["description"]
        desc_line = f" ({description})" if description else ""
        try:
            execution = await sandbox_mgr.start_execution(session_id, command, timeout, is_admin)
            self._tasks[task_id]["execution"] = execution
            await execution.wait(timeout=None if timeout == -1 else timeout + 5)
            output = execution.get_stdout() + execution.get_stderr()
            code = execution.returncode
            result = f"$ {command}\n{output}\n退出码: {code}"
            self._tasks[task_id].update({"status": "done", "result": result})
            note = f"[后台任务完成] ID: {task_id}{desc_line}\n{result}"
        except Exception as e:
            result = str(e)
            self._tasks[task_id].update({"status": "error", "result": result})
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
