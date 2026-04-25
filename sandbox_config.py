from dataclasses import dataclass, field
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
    custom_mounts: list[dict] = field(default_factory=list)
    sandbox_symlinks: list[dict] = field(default_factory=list)
    path: list[str] = field(default_factory=lambda: ["/usr/local/bin", "/usr/bin", "/bin", "/usr/local/sbin", "/usr/sbin", "/sbin"])
    custom_env: list[str] = field(default_factory=list)

    @property
    def skills_dir(self) -> str:
        """OpenClaw 技能目录路径"""
        return os.path.join(os.path.dirname(os.path.dirname(self.data_dir)), "skills")
