import re
import asyncio
import os
import tempfile
import shutil
import json
import hashlib
from astrbot.api.star import Context, Star
from astrbot.api.event import filter
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.message_event_result import MessageChain
from .tools.execute_shell import ExecuteShellTool

class SandboxManager:
    """沙箱管理器"""
    def __init__(self, data_dir: str):
        self.sandboxes = {}
        self.uid_map_file = os.path.join(data_dir, "nsjail_uid_map.json")
        self.uid_map = self._load_uid_map()
    
    def _load_uid_map(self) -> dict:
        if os.path.exists(self.uid_map_file):
            try:
                with open(self.uid_map_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载 UID 映射失败: {e}")
        return {}
    
    def _save_uid_map(self):
        try:
            os.makedirs(os.path.dirname(self.uid_map_file), exist_ok=True)
            with open(self.uid_map_file, 'w') as f:
                json.dump(self.uid_map, f)
        except Exception as e:
            logger.error(f"保存 UID 映射失败: {e}")
    
    def get_uid_for_session(self, session_id: str) -> int:
        if session_id in self.uid_map:
            return self.uid_map[session_id]
        
        hash_value = int(hashlib.sha256(session_id.encode()).hexdigest()[:8], 16)
        candidate_uid = 10000 + (hash_value % 50000)
        
        used_uids = set(self.uid_map.values())
        while candidate_uid in used_uids:
            candidate_uid += 1
            if candidate_uid >= 60000:
                candidate_uid = 10000
        
        self.uid_map[session_id] = candidate_uid
        self._save_uid_map()
        logger.info(f"为会话 {session_id} 分配 UID: {candidate_uid}")
        return candidate_uid
    
    def create_sandbox(self, session_id: str) -> tuple[str, int]:
        if session_id in self.sandboxes:
            info = self.sandboxes[session_id]
            return info['dir'], info['uid']
        
        uid = self.get_uid_for_session(session_id)
        clean_session_id = re.sub(r'[^a-zA-Z0-9_-]', '_', session_id)[:50]
        sandbox_dir = tempfile.mkdtemp(prefix=f'nsjail_{clean_session_id}_')
        
        try:
            os.chown(sandbox_dir, 99999, 99999)
            os.chmod(sandbox_dir, 0o755)
        except Exception as e:
            logger.warning(f'设置目录权限失败: {e}')
        
        self.sandboxes[session_id] = {'dir': sandbox_dir, 'uid': uid}
        logger.info(f'创建沙箱: {sandbox_dir} (UID: {uid})')
        return sandbox_dir, uid
    
    def get_sandbox(self, session_id: str) -> tuple[str, int]:
        info = self.sandboxes.get(session_id)
        if info:
            return info['dir'], info['uid']
        return None, None
    
    def destroy_sandbox(self, session_id: str):
        info = self.sandboxes.pop(session_id, None)
        if info and os.path.exists(info['dir']):
            shutil.rmtree(info['dir'])
            logger.info(f"销毁沙箱: {info['dir']}")

class NsjailPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.max_timeout = config.get("max_timeout", 60)
        self.enable_network = config.get("enable_network", False)
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "config")
        self.sandbox_mgr = SandboxManager(data_dir)
        
        tool = ExecuteShellTool()
        tool.plugin_instance = self
        self.context.add_llm_tools(tool)
    
    @filter.command("nsjail")
    async def handle_nsjail_command(self, event: AstrMessageEvent):
        """处理 /nsjail 命令"""
        # 移除 /nsjail 前缀和可能的空格
        full_msg = event.message_str.strip()
        if full_msg.startswith('/nsjail'):
            command = full_msg[7:].strip()  # 移除 '/nsjail' (7个字符)
        elif full_msg.startswith('nsjail'):
            command = full_msg[6:].strip()  # 移除 'nsjail' (6个字符)
        else:
            command = full_msg
        
        if not command:
            yield event.plain_result("用法: /nsjail <命令>")
            return
        
        if len(command) > 1000:
            yield event.plain_result("命令过长（最大 1000 字符）")
            return
        
        session_id = event.session_id or "default"
        output, returncode = await self.execute_in_sandbox(session_id, command)
        
        response = f"退出码: {returncode}\n输出:\n{output}"
        yield event.plain_result(response[:2000])
    
    async def execute_in_sandbox(self, session_id: str, command: str, timeout: int = 30) -> tuple[str, int]:
        timeout = min(timeout, self.max_timeout)
        
        sandbox_dir, uid = self.sandbox_mgr.get_sandbox(session_id)
        if not sandbox_dir:
            sandbox_dir, uid = self.sandbox_mgr.create_sandbox(session_id)
        
        astrbot_skills_dir = "/AstrBot/data/skills"
        
        nsjail_cmd = [
            "nsjail",
            "--mode", "o",
            "--user", "99999",
            "--group", "99999",
            "--disable_clone_newuser",
            "--disable_clone_newnet",
            "--bindmount", f"{sandbox_dir}:/workspace:rw",
            "--bindmount", "/usr:/usr:ro",
            "--bindmount", "/lib:/lib:ro",
            "--bindmount", "/lib64:/lib64:ro",
            "--bindmount", "/bin:/bin:ro",
            "--bindmount", "/sbin:/sbin:ro",
        ]
        
        if self.enable_network:
            nsjail_cmd.extend([
                "--bindmount", "/etc/resolv.conf:/etc/resolv.conf:ro",
                "--bindmount", "/etc/ssl:/etc/ssl:ro"
            ])
        
        if os.path.exists(astrbot_skills_dir):
            nsjail_cmd.extend(["--bindmount", f"{astrbot_skills_dir}:{astrbot_skills_dir}:ro"])
        
        nsjail_cmd.extend([
            "--cwd", "/workspace",
            "--time_limit", str(timeout),
            "--max_cpus", "1",
            "--rlimit_as", "512",
            "--rlimit_fsize", "100",
            "--quiet",
            "--",
            "/bin/bash", "-c", command
        ])
        
        logger.info(f"执行 nsjail 命令: {' '.join(nsjail_cmd)}")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *nsjail_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
            return stdout.decode('utf-8', errors='replace'), proc.returncode
        except asyncio.TimeoutError:
            return "执行超时", -1
        except Exception as e:
            return f"执行错误: {str(e)}", -1
    
    async def terminate(self):
        for session_id in list(self.sandbox_mgr.sandboxes.keys()):
            self.sandbox_mgr.destroy_sandbox(session_id)
