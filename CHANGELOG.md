# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-04-26

### Added
- 后台执行模式：`execute_shell` 工具支持 `background=true` 参数，任务完成后自动将结果发送到会话并唤醒 Agent 处理
- 新增 `query_background_shell_execution` 工具：查询后台任务状态及实时输出
- 新增 `list_background_shell_executions` 工具：列出所有正在运行的后台任务
- 新增 `cancel_background_shell_execution` 工具：立即终止后台任务
- 新增 `/exec_bg` 命令：通过聊天命令触发后台执行
- 新增 `enable_background` / `background_max_timeout` 配置项控制后台模式
- `Execution` 对象支持运行中实时查询 stdout/stderr
- AstrBot temp 目录以只读方式挂载进沙箱，LLM 可直接访问用户发送的文件

### Changed
- `/nsjail` 命令重命名为 `/exec`
- `execute_in_sandbox` 重构为 `start_execution`，立即返回 `Execution` 对象
- cgroup V2 检测移入 `SandboxManager.__init__`，不再由外部传入
- 启动时沙箱清理移入 `SandboxManager.__init__`
- data/skills 目录挂载权限统一通过 `_apply_custom_mounts` 处理
- 工具代码拆分至 `tools/` 目录，每个工具独立文件
- 后台任务管理封装为 `BackgroundTaskManager` 类
- stdout/stderr 分别独立截断（各 2000 字符）
- 工具描述新增系统信息和后台模式使用说明

### Fixed
- `/exec` 命令超时时间改为使用 `max_timeout` 配置，不再硬编码 30s
- 移除 Computer Use 限制提示词（通过 `on_llm_request` 钩子）
- 后台任务完成后从注册表移除，避免内存泄漏

### Docker
- 新增 `ffmpeg` 和 `pipx` 到镜像
- `pipx` 移至 Python 工具层

## [0.1.0] - 2026-03-14

### Added
- Initial release of AstrBot NsJail plugin
- Secure sandbox execution using nsjail
- Support for Python, Node.js, and Shell commands
- Network access control (enable/disable)
- Resource limits (CPU and memory)
- Python venv support with python3.13-venv
- SSL/TLS certificate support for HTTPS requests
- Comprehensive test suite (99.3% pass rate)

### Features
- **Sandbox Isolation**: User/network/filesystem isolation using nsjail
- **Language Support**: Python 3.13, Node.js 24, Shell (bash)
- **Package Managers**: pip, npm, yarn, uv, pdm, poetry
- **Network Control**: Optional network access with DNS and SSL support
- **Resource Limits**: Configurable CPU and memory limits via cgroups v2
- **Session Management**: Per-user sandbox directories with automatic cleanup

### Security
- Non-root execution (UID 99999)
- Filesystem isolation with read-only system mounts
- Network namespace isolation (optional)
- Process limits and resource constraints

### Testing
- 136 test cases covering all major functionality
- 135/136 tests passing (99.3%)
- Test categories: Python, Shell, Node.js, Network, File Operations, Security

### Documentation
- Complete API documentation
- Test framework and guidelines
- Deployment instructions
- Configuration examples

[0.1.0]: https://github.com/ssttkkl/astrbot-plugin-nsjail/releases/tag/v0.1.0
