# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
