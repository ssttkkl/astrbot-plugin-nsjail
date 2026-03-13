import re
import asyncio
import os
import tempfile
import shutil
import json
import hashlib
from astrbot.api import logger


class SandboxManager:
    """沙箱管理器"""
    def __init__(self, data_dir: str, max_timeout: int = 60, enable_network: bool = False, memory_limit_mb: int = -1, cpu_limit_percent: int = -1):
        self.sandboxes = {}
        self.max_timeout = max_timeout
        self.enable_network = enable_network
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit_percent = cpu_limit_percent
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
        import time
        timestamp = int(time.time())
        sandbox_dir = tempfile.mkdtemp(prefix=f'nsjail_{clean_session_id}_{timestamp}_')
        
        try:
            os.chown(sandbox_dir, 99999, 99999)
            os.chmod(sandbox_dir, 0o755)
        except Exception as e:
            logger.warning(f'设置目录权限失败: {e}')
        
        self.sandboxes[session_id] = {'dir': sandbox_dir, 'uid': uid, 'created_at': timestamp}
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
    
    async def execute_in_sandbox(self, session_id: str, command: str, timeout: int = 30) -> tuple[str, int]:
        """在沙箱中执行命令"""
        timeout = min(timeout, self.max_timeout)
        
        sandbox_dir, uid = self.get_sandbox(session_id)
        if not sandbox_dir:
            sandbox_dir, uid = self.create_sandbox(session_id)
        
        astrbot_skills_dir = "/AstrBot/data/skills"
        
        nsjail_cmd = [
            "nsjail",
            "--mode", "o",
            "--user", "99999",
            "--group", "99999",
            "--disable_clone_newuser",
            "--bindmount", f"{sandbox_dir}:/workspace:rw",
            "--bindmount", "/usr:/usr:ro",
            "--bindmount", "/lib:/lib:ro",
            "--bindmount", "/lib64:/lib64:ro",
            "--bindmount", "/bin:/bin:ro",
            "--bindmount", "/sbin:/sbin:ro",
            "--bindmount", "/tmp:/tmp:rw",
            "--bindmount", "/sandbox-cache:/sandbox-cache:rw",
            "--bindmount", "/dev/null:/dev/null:rw",
            "--bindmount", "/dev/urandom:/dev/urandom:ro",
        ]
        
        # 网络配置：默认隔离，配置启用时才共享宿主网络
        if self.enable_network:
            nsjail_cmd.append("--disable_clone_newnet")
            nsjail_cmd.extend([
                "--bindmount", "/etc/resolv.conf:/etc/resolv.conf:ro",
                "--bindmount", "/etc/ssl:/etc/ssl:ro"
            ])
        
        if os.path.exists(astrbot_skills_dir):
            nsjail_cmd.extend(["--bindmount", f"{astrbot_skills_dir}:{astrbot_skills_dir}:ro"])
        
        nsjail_cmd.extend([
            "--cwd", "/workspace",
            "--time_limit", str(timeout),
            "--rlimit_fsize", "100",
            "--rlimit_nproc", "50",
        ])
        
        # 使用 Cgroup V2 进行资源限制（如果配置了）
        if self.memory_limit_mb > 0 or self.cpu_limit_percent > 0:
            nsjail_cmd.extend([
                "--use_cgroupv2",
                "--cgroupv2_mount", "/sys/fs/cgroup",
            ])
            
            if self.memory_limit_mb > 0:
                memory_bytes = self.memory_limit_mb * 1024 * 1024
                nsjail_cmd.extend(["--cgroup_mem_max", str(memory_bytes)])
            
            if self.cpu_limit_percent > 0:
                # CPU 限制：百分比转换为毫秒/秒
                cpu_ms_per_sec = self.cpu_limit_percent * 10
                nsjail_cmd.extend(["--cgroup_cpu_ms_per_sec", str(cpu_ms_per_sec)])
        
        nsjail_cmd.extend([
            "--clear_env",
            "--env", "PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin",
            "--env", "UV_CACHE_DIR=/sandbox-cache/uv",
            "--env", "HOME=/workspace",
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

    def cleanup_old_sandboxes(self):
        """清理超过3天的沙箱目录"""
        import time
        import glob
        
        current_time = time.time()
        three_days_ago = current_time - (3 * 24 * 3600)
        
        # 查找所有 nsjail_ 开头的临时目录
        temp_dir = tempfile.gettempdir()
        pattern = os.path.join(temp_dir, 'nsjail_*')
        
        cleaned_count = 0
        for sandbox_path in glob.glob(pattern):
            try:
                # 从目录名提取时间戳
                parts = os.path.basename(sandbox_path).split('_')
                if len(parts) >= 3 and parts[-1].isdigit():
                    timestamp = int(parts[-1])
                    if timestamp < three_days_ago:
                        shutil.rmtree(sandbox_path)
                        logger.info(f"清理过期沙箱: {sandbox_path}")
                        cleaned_count += 1
            except Exception as e:
                logger.warning(f"清理沙箱失败 {sandbox_path}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个过期沙箱")
