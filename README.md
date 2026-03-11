# AstrBot NsJail 沙箱插件

为 AstrBot 提供基于 NsJail 的安全代码执行环境，支持 LLM 函数调用。

## 功能特性

- 🔒 **文件系统隔离** - 通过命名空间隔离，独立的工作目录
- 📦 **独立沙箱环境** - 每个会话拥有独立的 workspace
- ⚡ **资源限制** - CPU、内存、文件大小、执行时间全面限制
- 🔄 **自动管理** - 沙箱自动创建、复用和销毁
- 🤖 **LLM 集成** - 作为函数工具供 LLM 调用
- 🚀 **完全复用宿主软件** - Python、Node.js、Git 等全部可用

## 技术方案

### 隔离架构

沙箱通过 bindmount 挂载宿主容器的系统目录，实现软件复用和隔离：

- , ,  等系统目录只读挂载
-  为独立的可读写工作目录
- 每个会话有独立的 workspace，会话结束后销毁

### NsJail 配置



### 安全保障

| 隔离层级 | 实现方式 | 效果 |
|---------|---------|------|
| 文件系统 | Mount namespace + bindmount | 只能访问挂载的目录 |
| 进程 | PID namespace | 无法看到其他进程 |
| 网络 | 禁用网络命名空间 | 共享宿主网络 |
| 资源 | rlimit | CPU/内存/文件大小限制 |
| 用户权限 | UID 99999 | 非 root 运行 |

## 部署方式

### Docker Compose（推荐）



**注意：** 需要  权限以支持挂载命名空间。

## 使用方法

### LLM 函数调用

插件会自动注册  函数工具，LLM 可以直接调用：



### 配置

配置文件位置：`data/config/astrbot_plugin_nsjail_config.json`



| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `max_timeout` | int | 60 | 最大执行超时时间（秒） |
| `enable_network` | bool | false | 是否允许沙箱访问网络 |

## 资源限制

| 资源 | 默认限制 | 说明 |
|------|---------|------|
| 执行时间 | 30秒 | 可通过参数调整，最大 60 秒 |
| 内存 | 512MB | 超出会被 OOM kill |
| 文件大小 | 100MB | 单个文件最大 |
| CPU | 1核 | 限制 CPU 使用 |

## 预装软件

沙箱完全复用宿主容器的软件，包括但不限于：
- Python 3.12+
- Node.js 24+
- Git
- Curl
- 所有已安装的 Python 包和 Node.js 模块

## 常见问题

### Q: 为什么需要 CAP_SYS_ADMIN 权限？

A: nsjail 的挂载命名空间功能需要此权限。相比 privileged 模式，这是更精细的权限控制。

### Q: 沙箱能访问网络吗？

A: 默认共享宿主网络。如需完全隔离，可启用网络命名空间（需要额外配置）。

### Q: 如何添加更多软件包？

A: 直接在宿主容器中安装即可，沙箱会自动复用。例如：


### Q: /workspace 目录会持久化吗？

A: 不会。每个会话结束后，workspace 会被自动销毁，确保会话间隔离。

## 开发



## 许可证

MIT License

## 相关链接

- [NsJail](https://github.com/google/nsjail)
- [AstrBot](https://github.com/Soulter/AstrBot)
