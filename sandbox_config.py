from dataclasses import dataclass
import os


@dataclass
class SandboxConfig:
    """沙箱配置"""
    data_dir: str
    max_timeout: int = 60
    enable_network: bool = False
    memory_limit_mb: int = -1
    cpu_limit_percent: int = -1
    cpu_cores_limit: int = -1
    process_limit: int = 50
    data_write_permission: str = "none"
    skills_write_permission: str = "none"
    custom_mounts: list[dict] | None = None
    sandbox_symlinks: list[dict] | None = None
    path: list[str] | None = None
    custom_env: list[str] | None = None
    cgroup_available: bool = False
    
    def __post_init__(self):
        if self.custom_mounts is None:
            self.custom_mounts = []
        if self.sandbox_symlinks is None:
            self.sandbox_symlinks = []
        if self.path is None:
            self.path = ["/usr/local/bin", "/usr/bin", "/bin", "/usr/local/sbin", "/usr/sbin", "/sbin"]
        if self.custom_env is None:
            self.custom_env = []
    
    @property
    def skills_dir(self) -> str:
        """OpenClaw 技能目录路径"""
        return os.path.join(os.path.dirname(os.path.dirname(self.data_dir)), "skills")
