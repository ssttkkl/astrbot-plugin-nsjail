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
    
    
    def create_sandbox(self, session_id: str) -> dict:
        if session_id in self.sandboxes:
            return self.sandboxes[session_id]
        
        clean_session_id = re.sub(r'[^a-zA-Z0-9_-]', '_', session_id)[:50]
        sandbox_dir = os.path.join(self.workspaces_dir, clean_session_id)
        
        # 创建工作目录
        os.makedirs(sandbox_dir, exist_ok=True)
        
        # 创建会话独立的 /tmp 目录（在宿主机 /tmp 下）
        tmp_dir = f"/tmp/nsjail_{clean_session_id}"
        os.makedirs(tmp_dir, exist_ok=True)
        
        try:
            os.chown(sandbox_dir, 99999, 99999)
            os.chmod(sandbox_dir, 0o755)
            os.chown(tmp_dir, 99999, 99999)
            os.chmod(tmp_dir, 0o755)
        except Exception as e:
            logger.warning(f'设置目录权限失败: {e}')
        
        sandbox_info = {'dir': sandbox_dir, 'tmp_dir': tmp_dir}
        self.sandboxes[session_id] = sandbox_info
        logger.info(f'创建沙箱: {sandbox_dir}, tmp: {tmp_dir}')
        return sandbox_info
    
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
                
                # 去掉 /workspace 前缀，因为 sandbox_dir 已经会被挂载为 /workspace
                target_relative = target.removeprefix('/workspace/')
                target_path = os.path.join(sandbox_dir, target_relative)
                
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
            
            # 变量替换
            host_path = host_path.replace("$(DATA)", os.path.join(self.config.data_dir, "data"))
            
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
            
            # 如果是可写挂载，检查目录权限
            if mount_mode == "rw":
                try:
                    stat_info = os.stat(host_path)
                    # 检查是否属于 UID 99999 或者 others 有写权限
                    if stat_info.st_uid != 99999 and not (stat_info.st_mode & 0o002):
                        logger.warning(f"目录 {host_path} 可能没有 UID 99999 的写入权限，如果遇到权限错误，请执行: sudo chown -R 99999:99999 {host_path}")
                except Exception as e:
                    logger.warning(f"无法检查目录权限 {host_path}: {e}")
            
            nsjail_cmd.extend(["--bindmount", f"{host_path}:{sandbox_path}:{mount_mode}"])
            logger.info(f"添加自定义挂载: {host_path} -> {sandbox_path} ({mount_mode})")
    
    def get_sandbox(self, session_id: str) -> dict:
        return self.sandboxes.get(session_id)
    
    def destroy_sandbox(self, session_id: str):
        info = self.sandboxes.pop(session_id, None)
        self._create_locks.pop(session_id, None)  # 清理锁释放内存
        if info:
            if os.path.exists(info['dir']):
                shutil.rmtree(info['dir'], ignore_errors=True)
                logger.info(f"销毁沙箱: {info['dir']}")
            if 'tmp_dir' in info and os.path.exists(info['tmp_dir']):
                shutil.rmtree(info['tmp_dir'], ignore_errors=True)
                logger.info(f"清理临时目录: {info['tmp_dir']}")
    
    def cleanup_all_sandboxes(self):
        """启动时清理所有沙箱目录"""
        import glob
        
        # 清理 workspace 目录
        if os.path.exists(self.workspaces_dir):
            for sandbox_path in glob.glob(os.path.join(self.workspaces_dir, '*')):
                try:
                    shutil.rmtree(sandbox_path, ignore_errors=True)
                    logger.info(f"清理沙箱: {sandbox_path}")
                except Exception as e:
                    logger.warning(f"清理沙箱失败 {sandbox_path}: {e}")
        
        # 清理 /tmp 目录
        for tmp_path in glob.glob('/tmp/nsjail_*'):
            try:
                shutil.rmtree(tmp_path, ignore_errors=True)
                logger.info(f"清理临时目录: {tmp_path}")
            except Exception as e:
                logger.warning(f"清理临时目录失败 {tmp_path}: {e}")
    
    def resolve_sandbox_path(self, session_id: str, sandbox_path: str) -> str:
        """将沙箱内路径映射到宿主机真实路径"""
        info = self.sandboxes.get(session_id)
        if not info:
            return None
        
        sandbox_dir = info['dir']
        tmp_dir = info.get('tmp_dir')
        
        # 检查自定义挂载路径
        for mount in self.config.custom_mounts:
            if not isinstance(mount, dict):
                continue
            sandbox_mount = mount.get("sandbox_path", "").strip()
            host_path = mount.get("host_path", "").strip()
            if sandbox_mount and host_path and sandbox_path.startswith(sandbox_mount):
                rel_path = sandbox_path[len(sandbox_mount):].lstrip('/')
                return os.path.join(os.path.expanduser(host_path), rel_path)
        
        # 标准路径映射
        if sandbox_path.startswith('/workspace/'):
            return os.path.join(sandbox_dir, sandbox_path[11:])
        elif sandbox_path.startswith('/workspace'):
            return os.path.join(sandbox_dir, sandbox_path[10:])
        elif sandbox_path.startswith('/tmp/') and tmp_dir:
            return os.path.join(tmp_dir, sandbox_path[5:])
        elif sandbox_path.startswith('/tmp') and tmp_dir:
            return os.path.join(tmp_dir, sandbox_path[4:])
        else:
            return os.path.join(sandbox_dir, sandbox_path.lstrip('/'))
    
    async def execute_in_sandbox(self, session_id: str, command: str, timeout: int = 30, is_admin: bool = False) -> tuple[str, int]:
        """在沙箱中执行命令"""
        timeout = min(timeout, self.config.max_timeout)
        
        # 获取或创建该会话的锁
        if session_id not in self._create_locks:
            self._create_locks[session_id] = asyncio.Lock()
        
        # 使用锁保护沙箱创建
        async with self._create_locks[session_id]:
            info = self.get_sandbox(session_id)
            if not info:
                info = self.create_sandbox(session_id)
        
        # 安全地获取路径
        sandbox_dir = info.get('dir')
        tmp_dir = info.get('tmp_dir')
        
        # 兜底检查
        if not sandbox_dir or not tmp_dir:
            return "沙箱创建或获取失败，请检查系统日志。", -1
        
        # AstrBot 技能目录
        astrbot_skills_dir = self.config.skills_dir
        
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
        
        # 添加独立的共享内存（64MB）
        nsjail_cmd.extend(["--mount", "none:/dev/shm:tmpfs:size=67108864"])
        
        # 添加字体配置（用于图表渲染等）
        if os.path.exists("/etc/fonts"):
            nsjail_cmd.extend(["--bindmount", "/etc/fonts:/etc/fonts:ro"])
        
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
            nsjail_cmd.extend(["--bindmount", f"{astrbot_skills_dir}:{astrbot_skills_dir}:{skills_mount_mode}"])
        
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
        
        # 构建 PATH 环境变量
        path_value = ":".join(self.config.path)
        
        nsjail_cmd.extend([
            "--env", f"PATH={path_value}",
            "--env", "HOME=/workspace",
            "--env", "NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt",
            "--env", "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt",
        ])
        
        # 添加自定义环境变量
        for env_var in self.config.custom_env:
            if "=" in env_var:
                nsjail_cmd.extend(["--env", env_var])
        
        nsjail_cmd.extend([
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
