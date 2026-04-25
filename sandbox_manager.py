import re
import glob
import asyncio
import os
import shutil
import time
import aiofiles
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path
from .sandbox_config import SandboxConfig


class Execution:
    def __init__(self, proc: asyncio.subprocess.Process, timeout: float | None = None, tmp_dir: str | None = None):
        self._proc = proc
        self._done = False
        self._timed_out = False
        self._returncode: int | None = None
        self._tmp_dir = tmp_dir
        if tmp_dir:
            results_dir = os.path.join(tmp_dir, "tool-results")
            os.makedirs(results_dir, exist_ok=True)
            ts = int(time.time() * 1000)
            self._stdout_path = os.path.join(results_dir, f"{ts}.stdout")
            self._stderr_path = os.path.join(results_dir, f"{ts}.stderr")
        else:
            self._stdout_path = None
            self._stderr_path = None
        self._reader_task = asyncio.create_task(self._read_streams(timeout))

    async def _read_streams(self, timeout: float | None):
        async def drain(stream, path):
            if not stream:
                return
            if not path:
                async for _ in stream:
                    pass
                return
            async with aiofiles.open(path, "wb") as f:
                async for chunk in stream:
                    await f.write(chunk)

        try:
            await asyncio.wait_for(asyncio.gather(
                drain(self._proc.stdout, self._stdout_path),
                drain(self._proc.stderr, self._stderr_path),
            ), timeout=timeout)
        except asyncio.TimeoutError:
            self._timed_out = True
            await self.kill()
        self._returncode = self._proc.returncode
        self._done = True

    async def _read_file(self, path: str | None) -> str:
        if not path or not os.path.exists(path):
            return ""
        async with aiofiles.open(path, "rb") as f:
            return (await f.read()).decode("utf-8", errors="replace")

    async def get_stdout(self) -> str:
        return await self._read_file(self._stdout_path)

    async def get_stderr(self) -> str:
        return await self._read_file(self._stderr_path)

    @property
    def returncode(self) -> int | None:
        return self._returncode

    @property
    def done(self) -> bool:
        return self._done

    @property
    def timed_out(self) -> bool:
        return self._timed_out

    async def wait(self) -> int:
        await self._reader_task
        return self._returncode

    _INLINE_LIMIT = 30 * 1024       # 30 KB
    _FILE_LIMIT   = 64 * 1024 * 1024  # 64 MB

    async def format_result(self, command: str) -> str:
        code = self._returncode if self._returncode is not None else -1
        prefix = "执行超时，当前输出" if self._timed_out else f"退出码: {code}"

        if self._stdout_path:
            stdout_size = os.path.getsize(self._stdout_path) if os.path.exists(self._stdout_path) else 0
            stderr_size = os.path.getsize(self._stderr_path) if self._stderr_path and os.path.exists(self._stderr_path) else 0
            total_size = stdout_size + stderr_size
            if total_size > self._INLINE_LIMIT:
                async def read_head(path, size) -> str:
                    if not path or size == 0:
                        return ""
                    limit = int(self._INLINE_LIMIT * size / total_size)
                    async with aiofiles.open(path, "rb") as f:
                        return (await f.read(limit)).decode("utf-8", errors="replace")
                stderr_part = await read_head(self._stderr_path, stderr_size)
                output = await read_head(self._stdout_path, stdout_size) + (f"\n[stderr]\n{stderr_part}" if stderr_part else "")
                return f"$ {command}\n{output}\n{prefix}\n输出过长，已写入文件（共 {total_size // 1024}KB）"

        stdout = await self.get_stdout()
        stderr = await self.get_stderr()
        for path in (self._stdout_path, self._stderr_path):
            if path and os.path.exists(path):
                os.unlink(path)
        output = stdout + (f"\n[stderr]\n{stderr}" if stderr else "")
        return f"$ {command}\n{output}\n{prefix}"

    async def kill(self):
        try:
            self._proc.kill()
            await self._proc.wait()
        except Exception:
            pass
        for path in (self._stdout_path, self._stderr_path):
            if path and os.path.exists(path):
                os.unlink(path)


class SandboxManager:
    """沙箱管理器"""
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.cgroup_available = self._check_cgroup()
        if not self.cgroup_available:
            self.config.memory_limit_mb = -1
            self.config.cpu_limit_percent = -1
        self.sandboxes = {}
        self.workspaces_dir = os.path.join(config.data_dir, "workspaces")
        os.makedirs(self.workspaces_dir, exist_ok=True)
        self._create_locks = {}
        self.cleanup_all_sandboxes()

    def _check_cgroup(self) -> bool:
        test_cgroup = "/sys/fs/cgroup/nsjail_test"
        try:
            os.makedirs(test_cgroup, exist_ok=True)
            with open(f"{test_cgroup}/cgroup.procs", "w") as f:
                f.write(str(os.getpid()))
            os.rmdir(test_cgroup)
            logger.info("Cgroup V2 可用，将启用内存和 CPU 限制")
            return True
        except Exception as e:
            logger.warning(f"Cgroup V2 不可用，将跳过内存和 CPU 使用率限制: {e}")
            return False
    
    
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
        
        # 创建符号链接
        self._create_sandbox_symlinks(sandbox_dir)
        
        sandbox_info = {'dir': sandbox_dir, 'tmp_dir': tmp_dir}
        self.sandboxes[session_id] = sandbox_info
        logger.info(f'创建沙箱: {sandbox_dir}, tmp: {tmp_dir}')
        return sandbox_info
    
    def _create_sandbox_symlinks(self, sandbox_dir: str):
        """创建沙箱内的符号链接"""
        logger.info(f'开始创建符号链接，配置项数量: {len(self.config.sandbox_symlinks)}')
        for symlink_config in self.config.sandbox_symlinks:
            source = symlink_config.get('source')
            target = symlink_config.get('target')
            logger.info(f'处理符号链接配置: source={source}, target={target}')
            if source and target:
                # 验证 target 必须在 /workspace 内（但不能是 /workspace 本身）
                if not target.startswith('/workspace/'):
                    logger.error(f'符号链接目标路径必须在 /workspace/ 内: {target}')
                    continue
                
                # 去掉 /workspace 前缀，因为 sandbox_dir 已经会被挂载为 /workspace
                target_relative = target.removeprefix('/workspace/')
                base = os.path.abspath(sandbox_dir)
                target_path = os.path.abspath(os.path.join(base, target_relative))
                if target_path != base and not target_path.startswith(base + os.sep):
                    logger.error(f'符号链接目标路径逃逸沙箱目录: {target}')
                    continue

                # 确保目标目录存在
                target_dir = os.path.dirname(target_path)
                os.makedirs(target_dir, exist_ok=True)
                
                # source 是沙箱内的路径，直接使用（符号链接在沙箱内创建）
                # 创建符号链接
                if not os.path.exists(target_path):
                    try:
                        os.symlink(source, target_path)
                        logger.info(f'创建符号链接: {target_path} -> {source}')
                    except Exception as e:
                        logger.error(f'创建符号链接失败 {target_path} -> {source}: {e}')
                else:
                    logger.warning(f'符号链接目标已存在，跳过: {target_path}')
    
    def _check_write_permission(self, path: str):
        """检查目录是否有 UID 99999 的写入权限"""
        try:
            stat_info = os.stat(path)
            if stat_info.st_uid != 99999 and not (stat_info.st_mode & 0o002):
                logger.warning(f"目录 {path} 可能没有 UID 99999 的写入权限，如果遇到权限错误，请执行: chown -R 99999:99999 {path}")
        except Exception as e:
            logger.warning(f"无法检查目录权限 {path}: {e}")
    
    def _apply_custom_mounts(self, nsjail_cmd: list, is_admin: bool, extra_mounts: list | None = None):
        """应用自定义路径映射"""
        mounts = (extra_mounts or []) + list(self.config.custom_mounts)
        for mount in mounts:
            if not isinstance(mount, dict):
                continue

            host_path = mount.get("host_path", "").strip()
            sandbox_path = mount.get("sandbox_path", "").strip()
            write_permission = mount.get("write_permission", "none")

            if not host_path or not sandbox_path:
                logger.warning(f"跳过无效的路径映射: {mount}")
                continue

            host_path = host_path.replace("$(DATA)", os.path.join(self.config.data_dir, "data"))
            host_path = os.path.expanduser(host_path)

            if not os.path.exists(host_path):
                try:
                    os.makedirs(host_path, exist_ok=True)
                    logger.info(f"自动创建挂载目录: {host_path}")
                except Exception as e:
                    logger.warning(f"无法创建目录 {host_path}，跳过挂载: {e}")
                    continue

            mount_mode = "ro"
            if write_permission == "all":
                mount_mode = "rw"
            elif write_permission == "admin" and is_admin:
                mount_mode = "rw"

            if mount_mode == "rw":
                self._check_write_permission(host_path)

            nsjail_cmd.extend(["--bindmount", f"{host_path}:{sandbox_path}:{mount_mode}"])
            logger.info(f"添加自定义挂载: {host_path} -> {sandbox_path} ({mount_mode})")
    
    def get_sandbox(self, session_id: str) -> dict:
        return self.sandboxes.get(session_id)
    
    def destroy_sandbox(self, session_id: str):
        info = self.sandboxes.pop(session_id, None)
        # 不移除锁，避免并发请求持有锁时产生竞态条件
        if info:
            if os.path.exists(info['dir']):
                shutil.rmtree(info['dir'], ignore_errors=True)
                logger.info(f"销毁沙箱: {info['dir']}")
            if 'tmp_dir' in info and os.path.exists(info['tmp_dir']):
                shutil.rmtree(info['tmp_dir'], ignore_errors=True)
                logger.info(f"清理临时目录: {info['tmp_dir']}")
    
    def cleanup_all_sandboxes(self):
        """启动时清理所有沙箱目录"""
        # 清理 workspace 目录
        if os.path.exists(self.workspaces_dir):
            for sandbox_path in glob.glob(os.path.join(self.workspaces_dir, '*')):
                shutil.rmtree(sandbox_path, ignore_errors=True)
                logger.info(f"清理沙箱: {sandbox_path}")
        
        # 清理 /tmp 目录
        for tmp_path in glob.glob('/tmp/nsjail_*'):
            shutil.rmtree(tmp_path, ignore_errors=True)
            logger.info(f"清理临时目录: {tmp_path}")
    
    def resolve_sandbox_path(self, session_id: str, sandbox_path: str) -> str:
        """将沙箱内路径映射到宿主机真实路径"""
        info = self.sandboxes.get(session_id)
        if not info:
            return None
        
        sandbox_dir = info['dir']
        tmp_dir = info.get('tmp_dir')
        data_dir = os.path.join(self.config.data_dir, "data")
        
        def safe_join(base: str, rel: str) -> str | None:
            base = os.path.abspath(base)
            target = os.path.abspath(os.path.join(base, rel))
            return target if target == base or target.startswith(base + os.sep) else None

        # 检查自定义挂载路径
        for mount in self.config.custom_mounts:
            if not isinstance(mount, dict):
                continue
            sandbox_mount = mount.get("sandbox_path", "").strip()
            host_path = mount.get("host_path", "").strip()
            if sandbox_mount and host_path and sandbox_path.startswith(sandbox_mount):
                rel_path = sandbox_path[len(sandbox_mount):].lstrip('/')
                return safe_join(os.path.expanduser(host_path), rel_path)

        # 标准路径映射
        if sandbox_path.startswith('/data'):
            return safe_join(data_dir, sandbox_path.removeprefix('/data').lstrip('/'))
        elif sandbox_path.startswith('/workspace'):
            return safe_join(sandbox_dir, sandbox_path.removeprefix('/workspace').lstrip('/'))
        elif sandbox_path.startswith('/tmp') and tmp_dir:
            return safe_join(tmp_dir, sandbox_path.removeprefix('/tmp').lstrip('/'))
        else:
            logger.warning(f"无法映射沙箱路径到宿主机路径: {sandbox_path}")
            return None
    
    async def start_execution(self, session_id: str, command: str, timeout: int = 30, is_admin: bool = False) -> "Execution":
        """在沙箱中启动命令，立即返回 Execution 对象"""
        # 如果 max_timeout 为 -1，表示无限制；否则取最小值
        if self.config.max_timeout != -1:
            timeout = min(timeout, self.config.max_timeout)
        
        # 获取或创建该会话的锁
        self._create_locks.setdefault(session_id, asyncio.Lock())
        
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
            raise RuntimeError("沙箱创建或获取失败，请检查系统日志。")
        
        # 确保 data 目录存在
        data_dir = os.path.join(self.config.data_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        builtin_mounts = [
            {"host_path": data_dir, "sandbox_path": "/data", "write_permission": self.config.data_write_permission},
        ]
        if os.path.exists(self.config.skills_dir):
            builtin_mounts.append({"host_path": self.config.skills_dir, "sandbox_path": self.config.skills_dir, "write_permission": self.config.skills_write_permission})

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
            "--bindmount", f"{tmp_dir}:/tmp:rw",
            "--bindmount", f"{get_astrbot_temp_path()}:{get_astrbot_temp_path()}:ro",
            "--bindmount", "/dev/null:/dev/null:rw",
            "--bindmount", "/dev/zero:/dev/zero:ro",
            "--bindmount", "/dev/urandom:/dev/urandom:ro",
        ]

        nsjail_cmd.extend(["--mount", "none:/dev/shm:tmpfs:size=67108864"])

        if os.path.exists("/etc/fonts"):
            nsjail_cmd.extend(["--bindmount", "/etc/fonts:/etc/fonts:ro"])

        if self.config.enable_network:
            nsjail_cmd.append("--disable_clone_newnet")
            nsjail_cmd.extend([
                "--bindmount", "/etc/resolv.conf:/etc/resolv.conf:ro",
                "--bindmount", "/etc/ssl:/etc/ssl:ro"
            ])
            if os.path.exists("/etc/pki"):
                nsjail_cmd.extend(["--bindmount", "/etc/pki:/etc/pki:ro"])
            if os.path.exists("/etc/ca-certificates"):
                nsjail_cmd.extend(["--bindmount", "/etc/ca-certificates:/etc/ca-certificates:ro"])

        self._apply_custom_mounts(nsjail_cmd, is_admin, extra_mounts=builtin_mounts)
        
        nsjail_cmd.extend([
            "--cwd", "/workspace",
            "--time_limit", str(timeout if timeout != -1 else 0),
            "--rlimit_fsize", "100",
            "--rlimit_nofile", "1024",
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

        proc = await asyncio.create_subprocess_exec(
            *nsjail_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return Execution(proc, timeout=None if timeout == -1 else timeout, tmp_dir=tmp_dir)
