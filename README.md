# AstrBot NsJail 沙箱插件

为 AstrBot 提供基于 NsJail 的安全代码执行环境，支持 LLM 函数调用。

## 功能特性

- 🔒 **文件系统隔离** - 通过命名空间隔离，独立的工作目录
- 📦 **独立沙箱环境** - 每个会话拥有独立的 workspace
- ⚡ **资源限制** - CPU、内存、文件大小、执行时间全面限制（支持 Cgroup V2）
- 🔄 **自动管理** - 沙箱自动创建、复用和销毁
- 🤖 **LLM 集成** - 作为函数工具供 LLM 调用
- 🚀 **完全复用宿主软件** - Python、Node.js、Git 等全部可用
- 📤 **图片和文件发送** - 支持从沙箱发送图片和文件到会话
- 💾 **持久化缓存** - uv 等工具的缓存持久化存储

## 技术方案

### 隔离架构

沙箱通过 bindmount 挂载宿主容器的系统目录，实现软件复用和隔离：

- `/usr`, `/lib`, `/bin` 等系统目录只读挂载
- `/workspace` 为独立的可读写工作目录
- 每个会话有独立的 workspace，会话结束后销毁

### NsJail 配置

```python
nsjail_args = [
    "/usr/local/bin/nsjail",
    "--user", "99999", "--group", "99999",
    "--disable_clone_newuser",      # 避免 newgidmap 错误
    "--bindmount", f"{sandbox_dir}:/workspace:rw",
    "--bindmount", "/usr:/usr:ro",
    "--bindmount", "/lib:/lib:ro",
    "--bindmount", "/lib64:/lib64:ro",
    "--bindmount", "/bin:/bin:ro",
    "--bindmount", "/sbin:/sbin:ro",
    "--bindmount", "/tmp:/tmp:rw",
    "--bindmount", "/sandbox-cache:/sandbox-cache:rw",  # 持久化缓存
    "--bindmount", "/dev/null:/dev/null:rw",
    "--bindmount", "/dev/urandom:/dev/urandom:ro",
    "--env", "PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin",
    "--env", "UV_CACHE_DIR=/sandbox-cache/uv",
    "--env", "HOME=/workspace",
    "--time_limit", str(timeout),
    "--rlimit_fsize", "100",
    "--cwd", "/workspace",
    "--quiet",
    "--",
    "/bin/bash", "-c", command
]
```

**关键配置说明：**
- `/proc` 默认挂载（供 uv 等工具检测系统信息）
- `/sandbox-cache` 持久化缓存目录（uv、yarn 等工具缓存）
- `HOME=/workspace` 环境变量（工具配置文件存储）
- 支持 Cgroup V2 资源限制（可选）

### 安全保障

| 隔离层级 | 实现方式 | 效果 |
|---------|---------|------|
| 文件系统 | Mount namespace + bindmount | 只能访问挂载的目录 |
| 进程 | PID namespace | 无法看到其他进程 |
| 网络 | 禁用网络命名空间 | 共享宿主网络（可配置） |
| 资源 | rlimit | CPU/内存/文件大小限制 |
| 用户权限 | UID 99999 | 非 root 运行 |

## 部署方式

### Docker Compose（推荐）

```yaml
services:
  astrbot:
    image: ghcr.io/ssttkkl/astrbot-plugin-nsjail:main
    container_name: astrbot
    restart: always
    ports:
      - "6185:6185"
    volumes:
      - ./data:/AstrBot/data
      - ./sandbox-cache:/sandbox-cache  # 持久化缓存目录
    cap_add:
      - SYS_ADMIN
      - NET_ADMIN
    security_opt:
      - apparmor=unconfined
      - seccomp=unconfined
    environment:
      - TZ=Asia/Shanghai
```

**关键配置说明：**
- `cap_add: [SYS_ADMIN]` - 必需，支持挂载命名空间
- `cap_add: [NET_ADMIN]` - 必需，支持网络命名空间配置
- `security_opt` - 必需，解除 AppArmor 和 Seccomp 限制
- `./sandbox-cache:/sandbox-cache` - 持久化缓存目录（uv、yarn 等）
- 不需要 `privileged: true`（已优化）

## 使用方法

### 1. LLM 函数调用

插件注册了以下 LLM 工具：

**execute_shell** - 执行 shell 命令
```python
execute_shell(command="python3 script.py", timeout=30)
```

**send_sandbox_image** - 发送沙箱内的图片
```python
send_sandbox_image(image_path="/workspace/chart.png")
```

**send_sandbox_file** - 发送沙箱内的文件
```python
send_sandbox_file(file_path="/workspace/report.txt")
```

### 2. 命令调用

在聊天中使用 `/nsjail` 命令：

```
/nsjail python3 -c "print('hello')"
/nsjail ls /workspace
/nsjail bash -c "echo test > file.txt && cat file.txt"
```

### 3. 配置

配置文件位置：`data/config/astrbot_plugin_nsjail_config.json`

```json
{
  "max_timeout": 60,
  "enable_network": false,
  "memory_limit_mb": 512,
  "cpu_limit_percent": 100
}
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| max_timeout | int | 60 | 最大执行超时时间（秒） |
| enable_network | bool | false | 是否允许沙箱访问网络 |
| memory_limit_mb | int | -1 | 内存限制（MB），-1 表示不限制（需 Cgroup V2） |
| cpu_limit_percent | int | -1 | CPU 限制（百分比），-1 表示不限制（需 Cgroup V2） |

## 资源限制

| 资源 | 默认限制 | 说明 |
|------|---------|------|
| 执行时间 | 30秒 | 可通过参数调整，最大 60 秒 |
| 内存 | 512MB | 超出会被 OOM kill |
| 文件大小 | 100MB | 单个文件最大 |
| CPU | 60秒 | CPU 时间限制 |

## 预装软件

沙箱完全复用宿主容器的软件，包括但不限于：
- Python 3.13+
- Node.js 24+
- Git
- Curl, wget
- 所有已安装的 Python 包和 Node.js 模块
- uv, pdm, poetry（Python 包管理）
- yarn（Node.js 包管理）
- Playwright（浏览器自动化）

## 持久化缓存

沙箱支持持久化缓存目录 `/sandbox-cache`，用于存储工具缓存：

```
/sandbox-cache/
├── uv/          # uv 缓存（UV_CACHE_DIR）
└── (未来可添加 yarn, npm, pip 等)
```

**优势**：
- 容器重启后缓存不丢失
- 加速依赖安装
- 统一管理，易于维护

## 会话管理

- 每个会话自动创建独立的沙箱目录
- 会话内多次命令共享同一沙箱（支持多步骤操作）
- 会话结束后自动销毁沙箱目录
- 每个会话分配唯一 UID（10000-60000）

## 常见问题

### Q: 为什么需要 CAP_SYS_ADMIN 权限？

A: nsjail 的挂载命名空间功能需要此权限。相比 privileged 模式，这是更精细的权限控制。

### Q: 沙箱能访问网络吗？

A: 默认共享宿主网络。如需完全隔离，可启用网络命名空间（需要额外配置）。

### Q: 如何添加更多软件包？

A: 直接在宿主容器中安装即可，沙箱会自动复用。例如：
```bash
docker exec -it astrbot pip install requests
docker exec -it astrbot npm install -g typescript
```

### Q: /workspace 目录会持久化吗？

A: 不会。每个会话结束后，workspace 会被自动销毁，确保会话间隔离。

### Q: 如何创建虚拟环境？

A: 支持 venv 创建和使用：
```bash
/nsjail /usr/bin/python3 -m venv /workspace/myenv
/nsjail /workspace/myenv/bin/pip install requests
/nsjail /workspace/myenv/bin/python script.py
```

## 测试

项目包含完整的测试套件（139个测试用例）：

```bash
cd agent-test
python3 test-script.py test-cases-python.json <username> <password_md5>
```

测试分类：
- Python (36个) - 基础功能、三方库、系统调用、多步骤
- Shell (47个) - Shell 脚本、系统命令
- Node.js (17个) - Node.js 功能
- 文件 (20个) - 文件操作和权限
- 网络 (20个) - HTTP 请求、DNS
- 安全 (8个) - 隔离测试、资源限制

详见 `agent-test/AGENTS.md`

## 许可证

MIT License

## 相关链接

- [NsJail](https://github.com/google/nsjail)
- [AstrBot](https://github.com/Soulter/AstrBot)
- [GitHub Repository](https://github.com/ssttkkl/astrbot-plugin-nsjail)
