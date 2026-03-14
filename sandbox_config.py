from dataclasses import dataclass
from typing import List, Dict


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
    custom_mounts: List[Dict] = None
    sandbox_symlinks: List[Dict] = None
    cgroup_available: bool = False
    
    def __post_init__(self):
        if self.custom_mounts is None:
            self.custom_mounts = []
        if self.sandbox_symlinks is None:
            self.sandbox_symlinks = []
