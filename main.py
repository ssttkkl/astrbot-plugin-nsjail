import asyncio
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
from .sandbox_manager import SandboxManager


class NsjailPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        max_timeout = config.get("max_timeout", 60)
        enable_network = config.get("enable_network", False)
        
        import os
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "config")
        self.sandbox_mgr = SandboxManager(data_dir, max_timeout, enable_network)
    
    @filter.llm_tool(name="execute_shell")
    async def execute_shell(self, event: AstrMessageEvent, command: str, timeout: int = 30):
        """在隔离的沙箱环境中执行 shell 命令。每个会话有独立的沙箱,文件系统隔离,资源受限。
        
        Args:
            command(string): 要执行的 shell 命令
            timeout(number): 超时时间(秒),默认30秒
        """
        session_id = event.session_id or "default"
        output, code = await self.sandbox_mgr.execute_in_sandbox(session_id, command, timeout)
        result = f"$ {command}\n{output}\n退出码: {code}"
        yield event.plain_result(result)
    
    @filter.command("nsjail")
    async def handle_nsjail_command(self, event: AstrMessageEvent):
        """处理 /nsjail 命令"""
        # 移除 /nsjail 前缀和可能的空格
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
        
        if len(command) > 1000:
            yield event.plain_result("命令过长（最大 1000 字符）")
            return
        
        session_id = event.session_id or "default"
        output, returncode = await self.sandbox_mgr.execute_in_sandbox(session_id, command)
        
        response = f"退出码: {returncode}\n输出:\n{output}"
        yield event.plain_result(response[:2000])
    
    async def terminate(self):
        for session_id in list(self.sandbox_mgr.sandboxes.keys()):
            self.sandbox_mgr.destroy_sandbox(session_id)
