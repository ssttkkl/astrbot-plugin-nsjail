import asyncio
import os
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import StarTools
from .sandbox_manager import SandboxManager
from .sandbox_config import SandboxConfig
from .tools import (
    ExecuteShellTool,
    get_tool_prompt,
    QueryBackgroundShellExecutionTool,
    ListBackgroundShellExecutionsTool,
    CancelBackgroundShellExecutionTool,
    SendSandboxImageTool,
    SendSandboxFileTool,
)


class NsjailPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        max_timeout = config.get("max_timeout", 60)
        enable_network = config.get("enable_network", False)
        memory_limit_mb = config.get("memory_limit_mb", -1)
        cpu_limit_percent = config.get("cpu_limit_percent", -1)
        cpu_cores_limit = config.get("cpu_cores_limit", -1)
        process_limit = config.get("process_limit", 50)
        data_write_permission = config.get("data_write_permission", "none")
        skills_write_permission = config.get("skills_write_permission", "none")
        custom_mounts = config.get("custom_mounts", [])
        sandbox_symlinks = config.get("sandbox_symlinks", [])

        # 过滤掉模板键
        sandbox_symlinks = [
            {k: v for k, v in item.items() if not k.startswith("__")}
            for item in sandbox_symlinks
            if isinstance(item, dict)
        ]

        path = config.get("path", None)
        custom_env = config.get("custom_env", [])
        enable_background = config.get("enable_background", True)
        background_max_timeout = config.get("background_max_timeout", 600)
        plugin_data_path = StarTools.get_data_dir()
        plugin_data_path.mkdir(parents=True, exist_ok=True)

        sandbox_config = SandboxConfig(
            data_dir=str(plugin_data_path),
            max_timeout=max_timeout,
            enable_network=enable_network,
            memory_limit_mb=memory_limit_mb,
            cpu_limit_percent=cpu_limit_percent,
            cpu_cores_limit=cpu_cores_limit,
            process_limit=process_limit,
            data_write_permission=data_write_permission,
            skills_write_permission=skills_write_permission,
            custom_mounts=custom_mounts,
            sandbox_symlinks=sandbox_symlinks,
            path=path,
            custom_env=custom_env,
            enable_background=enable_background,
            background_max_timeout=background_max_timeout,
        )

        self.sandbox_mgr = SandboxManager(sandbox_config)

        self.context.add_llm_tools(
            ExecuteShellTool(
                description=get_tool_prompt(sandbox_config),
                timeout_seconds=max_timeout,
                background_timeout_seconds=background_max_timeout,
                enable_background=enable_background,
                sandbox_mgr=self.sandbox_mgr,
            ),
            QueryBackgroundShellExecutionTool(),
            ListBackgroundShellExecutionsTool(),
            CancelBackgroundShellExecutionTool(),
            SendSandboxImageTool(sandbox_mgr=self.sandbox_mgr),
            SendSandboxFileTool(sandbox_mgr=self.sandbox_mgr),
        )

    _COMPUTER_USE_NOTICE = "User has not enabled the Computer Use feature. You cannot use shell or Python to perform skills. If you need to use these capabilities, ask the user to enable Computer Use in the AstrBot WebUI -> Config.\n"

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, request: ProviderRequest) -> None:
        request.system_prompt = request.system_prompt.replace(self._COMPUTER_USE_NOTICE, "")

    @filter.command("nsjail")
    async def handle_nsjail_command(self, event: AstrMessageEvent):
        """处理 /nsjail 命令"""
        full_msg = event.message_str.strip()
        if full_msg.startswith('/nsjail'):
            command = full_msg[7:].strip()
        elif full_msg.startswith('nsjail'):
            command = full_msg[6:].strip()
        else:
            command = full_msg

        if not command:
            yield event.plain_result("用法: /nsjail <命令>")
            return

        if len(command) > 65535:
            yield event.plain_result("命令过长（最大 65535 字符）")
            return

        session_id = event.session_id or "default"
        is_admin = event.is_admin()
        timeout = self.sandbox_mgr.config.max_timeout
        execution = await self.sandbox_mgr.start_execution(session_id, command, timeout=timeout, is_admin=is_admin)
        try:
            await execution.wait(timeout=None if timeout == -1 else timeout + 5)
        except asyncio.TimeoutError:
            pass
        output = execution.get_stdout() + execution.get_stderr()
        returncode = execution.returncode if execution.returncode is not None else -1

        response = f"退出码: {returncode}\n输出:\n{output}"
        if len(response) > 2000:
            head = response[:1000]
            tail = response[-900:]
            response = head + "\n...[内容已截断]...\n" + tail
        yield event.plain_result(response)

    @filter.command("nsjail-clean")
    async def handle_clean_command(self, event: AstrMessageEvent):
        """清理当前会话的沙箱目录"""
        session_id = event.session_id or "default"

        if session_id in self.sandbox_mgr.sandboxes:
            self.sandbox_mgr.destroy_sandbox(session_id)
            yield event.plain_result(f"✅ 已清理会话 {session_id} 的沙箱目录")
        else:
            yield event.plain_result(f"⚠️ 会话 {session_id} 没有沙箱目录")

    async def terminate(self):
        for session_id in list(self.sandbox_mgr.sandboxes.keys()):
            self.sandbox_mgr.destroy_sandbox(session_id)
