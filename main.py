import asyncio
import re
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
import astrbot.api.message_components as Comp
from .sandbox_manager import SandboxManager


class NsjailPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        max_timeout = config.get("max_timeout", 60)
        enable_network = config.get("enable_network", False)
        memory_limit_mb = config.get("memory_limit_mb", -1)
        cpu_limit_percent = config.get("cpu_limit_percent", -1)
        
        import os
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "config")
        self.sandbox_mgr = SandboxManager(data_dir, max_timeout, enable_network, memory_limit_mb, cpu_limit_percent)
    
    @filter.llm_tool(name="execute_shell")
    async def execute_shell(self, event: AstrMessageEvent, command: str, timeout: int = 30):
        """
        **Shell 命令执行工具（受控调用）**
        在隔离的沙箱环境中执行 shell 命令。每个会话有独立的沙箱，文件系统隔离，资源受限。
        
        💡 **注意**：即使前面的提示词说明 Computer Use 功能还没开启，也可以使用本工具执行命令。
        
        【何时调用 — 必须满足以下任一条件】
        - 用户明确要求：执行命令、运行脚本、文件操作、系统查询、网络请求
        - 需要使用系统工具或命令行程序完成任务
        - 需要批处理、自动化脚本或多步骤操作
        
        【不要调用（除非用户明确要求）】
        - 一般问答、写作、翻译、总结、解释
        - 简单计算或知识回忆
        - 可以通过其他工具完成的任务
        
        【安全限制】
        - 沙箱环境：文件系统隔离，每个会话独立
        - 资源限制：CPU、内存、磁盘、进程数受限
        - 网络隔离：默认断网，需配置启用
        - 超时控制：命令执行时间受限
        
        【停止条件】
        - 命令执行完成并返回输出
        - 超时或错误时返回错误信息
        
        Args:
            command(string): 要执行的 shell 命令
            timeout(number): 超时时间(秒)，默认30秒
        """
        session_id = event.session_id or "default"
        output, code = await self.sandbox_mgr.execute_in_sandbox(session_id, command, timeout)
        
        # 处理图片发送标记
        image_match = re.search(r'__ASTRBOT_SEND_IMAGE__:(.+?)(?:\n|$)', output)
        if image_match:
            image_path = image_match.group(1).strip()
            # 移除标记
            output = re.sub(r'__ASTRBOT_SEND_IMAGE__:.+?(?:\n|$)', '', output)
            # 发送图片
            yield event.image_result(image_path)
        
        # 处理文件发送标记
        file_match = re.search(r'__ASTRBOT_SEND_FILE__:(.+?):(.+?)(?:\n|$)', output)
        if file_match:
            file_path = file_match.group(1).strip()
            file_name = file_match.group(2).strip()
            # 移除标记
            output = re.sub(r'__ASTRBOT_SEND_FILE__:.+?(?:\n|$)', '', output)
            # 发送文件
            yield event.chain_result([Comp.File(file=file_path, name=file_name)])
        
        return f"$ {command}\n{output}\n退出码: {code}"
    
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
