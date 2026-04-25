import asyncio
import uuid
from astrbot.api.event import MessageChain

# task_id -> {"status": "running"|"done"|"error", "command": str, "result": str}
_tasks: dict = {}


def create_task(sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, umo) -> str:
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "running", "command": command, "result": None}
    asyncio.create_task(_run(task_id, sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, umo))
    return task_id


def query_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


async def _run(task_id, sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, umo):
    try:
        output, code = await sandbox_mgr.execute_in_sandbox(session_id, command, timeout, is_admin)
        result = f"$ {command}\n{output}\n退出码: {code}"
        _tasks[task_id] = {"status": "done", "command": command, "result": result}
        text = f"[后台任务完成] ID: {task_id}\n{result}"
    except Exception as e:
        result = str(e)
        _tasks[task_id] = {"status": "error", "command": command, "result": result}
        text = f"[后台任务失败] ID: {task_id}\n$ {command}\n{e}"
    await astrbot_context.send_message(umo, MessageChain().message(text))
