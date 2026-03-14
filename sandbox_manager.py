import re
import asyncio
import os
import tempfile
import shutil
from astrbot.api import logger
from .sandbox_config import SandboxConfig


class SandboxManager:
    """沙箱管理器"""
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.sandboxes = {}
        self.workspaces_dir = os.path.join(config.data_dir, "workspaces")
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._create_locks = {}  # 每个 session 的创建锁
    
    
    def create_sandbox(self, session_id: str) -> tuple[str, None]:
        if session_id in self.sandboxes:
            info = self.sandboxes[session_id]
            return info['dir'], None
        
        clean_session_id = re.sub(r'[^a-zA-Z0-9_-]', '_', session_id)[:50]
        import time
        timestamp = int(time.time())
        sandbox_dir = os.path.join(self.workspaces_dir, f"{clean_session_id}_{timestamp}")
        
        # 创建工作目录
        os.makedirs(sandbox_dir, exist_ok=True)
        
        # 创建会话独立的 /tmp 目录（在宿主机 /tmp 下）
        tmp_dir = f"/tmp/nsjail_{clean_session_id}_{timestamp}"
        os.makedirs(tmp_dir, exist_ok=True)
        
        self._create_sandbox_symlinks(sandbox_dir)
        
        try:
            os.chown(sandbox_dir, 99999, 99999)
            os.chmod(sandbox_dir, 0o755)
            os.chown(tmp_dir, 99999, 99999)
            os.chmod(tmp_dir, 0o755)
        except Exception as e:
            logger.warning(f'设置目录权限失败: {e}')
        
        self.sandboxes[session_id] = {'dir': sandbox_dir, 'tmp_dir': tmp_dir, 'created_at': timestamp}
        logger.info(f'创建沙箱: {sandbox_dir}, tmp: {tmp_dir}')
        return sandbox_dir, None
    
    def _create_sandbox_symlinks(self, sandbox_dir: str):
        """创建沙箱内的符号链接"""
        for symlink_config in self.config.sandbox_symlinks:
            source = symlink_config.get('source')
            target = symlink_config.get('target')
            if source and target:
                # 验证 target 必须在 /workspace 内（但不能是 /workspace 本身）
                if not target.startswith('/workspace/'):
                    logger.error(f'符号链接目标路径必须在 /workspace/ 内: {target}')
                    continue
                
                # 将相对于沙箱根的路径转换为绝对路径
                if not target.startswith('/'):
                    target_path = os.path.join(sandbox_dir, target)
                else:
                    target_path = os.path.join(sandbox_dir, target.lstrip('/'))
                
                # 确保目标目录存在
                target_dir = os.path.dirname(target_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # 创建符号链接
                if not os.path.exists(target_path):
                    try:
                        os.symlink(source, target_path)
                        logger.info(f'创建符号链接: {target_path} -> {source}')
                    except Exception as e:
                        logger.error(f'创建符号链接失败 {target_path} -> {source}: {e}')
    
    def _apply_custom_mounts(self, nsjail_cmd: list, is_admin: bool):
        """应用自定义路径映射"""
        for mount in self.config.custom_mounts:
            if not isinstance(mount, dict):
                continue
            
            host_path = mount.get("host_path", "").strip()
            sandbox_path = mount.get("sandbox_path", "").strip()
            write_permission = mount.get("write_permission", "none")
            
            if not host_path or not sandbox_path:
                logger.warning(f"跳过无效的路径映射: {mount}")
                continue
            
            # 展开 ~ 为实际路径
            host_path = os.path.expanduser(host_path)
            
            if not os.path.exists(host_path):
                logger.warning(f"宿主机路径不存在，跳过挂载: {host_path}")
                continue
            
            # 根据权限配置决定挂载模式
            mount_mode = "ro"
            if write_permission == "all":
                mount_mode = "rw"
            elif write_permission == "admin" and is_admin:
                mount_mode = "rw"
            
            nsjail_cmd.extend(["--bindmount", f"{host_path}:{sandbox_path}:{mount_mode}"])
            logger.info(f"添加自定义挂载: {host_path} -> {sandbox_path} ({mount_mode})")
    
    def get_sandbox(self, session_id: str) -> tuple[str, None]:
        info = self.sandboxes.get(session_id)
        if info:
            return info['dir'], None
        return None, None
    
    def destroy_sandbox(self, session_id: str):
        info = self.sandboxes.pop(session_id, None)
        if info:
            if os.path.exists(info['dir']):
                shutil.rmtree(info['dir'])
                logger.info(f"销毁沙箱: {info['dir']}")
            if 'tmp_dir' in info and os.path.exists(info['tmp_dir']):
                shutil.rmtree(info['tmp_dir'])
                logger.info(f"清理临时目录: {info['tmp_dir']}")
    
    async def execute_in_sandbox(self, session_id: str, command: str, timeout: int = 30, is_admin: bool = False) -> tuple[str, int]:
        """在沙箱中执行命令"""
        timeout = min(timeout, self.config.max_timeout)
        
        # 获取或创建该会话的锁
        if session_id not in self._create_locks:
            self._create_locks[session_id] = asyncio.Lock()
        
        # 使用锁保护沙箱创建
        async with self._create_locks[session_id]:
            sandbox_dir, _ = self.get_sandbox(session_id)
            if not sandbox_dir:
                sandbox_dir, _ = self.create_sandbox(session_id)
        
        # 获取会话独立的 tmp 目录
        info = self.sandboxes.get(session_id)
        tmp_dir = info.get('tmp_dir') if info else None
        
        # AstrBot 技能目录（相对于 data_dir 的上一级）
        astrbot_skills_dir = os.path.join(os.path.dirname(self.config.data_dir), "skills")
        
        # 根据配置和用户权限决定 /data 目录挂载权限
        data_mount_mode = "ro"
        if self.config.data_write_permission == "all":
            data_mount_mode = "rw"
        elif self.config.data_write_permission == "admin" and is_admin:
            data_mount_mode = "rw"
        
        # 确保 data 目录存在
        data_dir = os.path.join(self.config.data_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        
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
            "--bindmount", "/etc/alternatives:/etc/alternatives:ro",
            "--bindmount", f"{tmp_dir}:/tmp:rw",  # 会话独立的 tmp 目录
            "--bindmount", f"{data_dir}:/data:{data_mount_mode}",
            "--bindmount", "/dev/null:/dev/null:rw",
            "--bindmount", "/dev/urandom:/dev/urandom:ro",
        ]
        
        # 网络配置：默认隔离，配置启用时才共享宿主网络
        if self.config.enable_network:
            nsjail_cmd.append("--disable_clone_newnet")
            nsjail_cmd.extend([
                "--bindmount", "/etc/resolv.conf:/etc/resolv.conf:ro",
                "--bindmount", "/etc/ssl:/etc/ssl:ro"
            ])
            # 条件挂载证书路径（不同发行版）
            if os.path.exists("/etc/pki"):
                nsjail_cmd.extend(["--bindmount", "/etc/pki:/etc/pki:ro"])
            if os.path.exists("/etc/ca-certificates"):
                nsjail_cmd.extend(["--bindmount", "/etc/ca-certificates:/etc/ca-certificates:ro"])
        
        # 根据配置和用户权限决定 /skills 目录挂载权限
        skills_mount_mode = "ro"
        if self.config.skills_write_permission == "all":
            skills_mount_mode = "rw"
        elif self.config.skills_write_permission == "admin" and is_admin:
            skills_mount_mode = "rw"
        
        if os.path.exists(astrbot_skills_dir):
            nsjail_cmd.extend(["--bindmount", f"{astrbot_skills_dir}:/skills:{skills_mount_mode}"])
        
        # 添加自定义路径映射
        self._apply_custom_mounts(nsjail_cmd, is_admin)
        
        nsjail_cmd.extend([
            "--cwd", "/workspace",
            "--time_limit", str(timeout),
            "--rlimit_fsize", "100",
        ])
        
        # 进程数限制
        if self.config.process_limit > 0:
            nsjail_cmd.extend(["--rlimit_nproc", str(self.config.process_limit)])
        
        # CPU 核数限制
        if self.config.cpu_cores_limit > 0:
            nsjail_cmd.extend(["--max_cpus", str(self.config.cpu_cores_limit)])
        
        # 使用 Cgroup V2 进行资源限制（如果配置了）
        if self.config.memory_limit_mb > 0 or self.config.cpu_limit_percent > 0:
            nsjail_cmd.extend([
                "--use_cgroupv2",
                "--cgroupv2_mount", "/sys/fs/cgroup",
            ])
            
            if self.config.memory_limit_mb > 0:
                memory_bytes = self.config.memory_limit_mb * 1024 * 1024
                nsjail_cmd.extend(["--cgroup_mem_max", str(memory_bytes)])
            
            if self.config.cpu_limit_percent > 0:
                cpu_ms_per_sec = self.config.cpu_limit_percent * 10
                nsjail_cmd.extend(["--cgroup_cpu_ms_per_sec", str(cpu_ms_per_sec)])
        
        nsjail_cmd.extend([
            "--env", "PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin",
            "--env", "HOME=/workspace",
            "--env", "NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt",
            "--env", "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt",
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
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return "执行超时", -1
        except Exception as e:
            return f"执行错误: {str(e)}", -1

    def cleanup_old_sandboxes(self):
        """清理超过3天的沙箱目录和 /tmp 临时目录"""
        import time
        import glob
        
        current_time = time.time()
        three_days_ago = current_time - (3 * 24 * 3600)
        
        cleaned_count = 0
        
        # 清理 workspace 目录
        pattern = os.path.join(self.workspaces_dir, '*_*')
        for sandbox_path in glob.glob(pattern):
            try:
                basename = os.path.basename(sandbox_path)
                timestamp_str = basename.split('_')[-1]
                if timestamp_str.isdigit():
                    timestamp = int(timestamp_str)
                    if timestamp < three_days_ago:
                        shutil.rmtree(sandbox_path)
                        logger.info(f"清理过期沙箱: {sandbox_path}")
                        cleaned_count += 1
            except Exception as e:
                logger.warning(f"清理沙箱失败 {sandbox_path}: {e}")
        
        # 清理宿主机 /tmp 目录下的 nsjail 临时目录
        for tmp_path in glob.glob('/tmp/nsjail_*_*'):
            try:
                basename = os.path.basename(tmp_path)
                timestamp_str = basename.split('_')[-1]
                if timestamp_str.isdigit():
                    timestamp = int(timestamp_str)
                    if timestamp < three_days_ago:
                        shutil.rmtree(tmp_path)
                        logger.info(f"清理过期临时目录: {tmp_path}")
                        cleaned_count += 1
            except Exception as e:
                logger.warning(f"清理临时目录失败 {tmp_path}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个过期沙箱")
