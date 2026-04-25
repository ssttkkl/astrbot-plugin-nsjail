import asyncio
import uuid
from astrbot.api.event import MessageChain

# task_id -> {"status": "running"|"done"|"error", "command": str, "result": str}
_tasks: dict = {}


def create_task(sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, umo, description: str = "") -> str:
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "running", "command": command, "description": description, "result": None}
    asyncio.create_task(_run(task_id, sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, umo))
    return task_id


def query_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


async def _run(task_id, sandbox_mgr, astrbot_context, session_id, command, timeout, is_admin, umo):
    description = _tasks[task_id]["description"]
    desc_line = f" ({description})" if description else ""
    try:
        output, code = await sandbox_mgr.execute_in_sandbox(session_id, command, timeout, is_admin)
        result = f"$ {command}\n{output}\n退出码: {code}"
        _tasks[task_id] = {"status": "done", "command": command, "description": description, "result": result}
        text = f"[后台任务完成] ID: {task_id}{desc_line}\n{result}"
    except Exception as e:
        result = str(e)
        _tasks[task_id] = {"status": "error", "command": command, "description": description, "result": result}
        text = f"[后台任务失败] ID: {task_id}{desc_line}\n$ {command}\n{e}"
    await astrbot_context.send_message(umo, MessageChain().message(text))
