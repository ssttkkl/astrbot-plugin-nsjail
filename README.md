# AstrBot NsJail 沙箱插件

为 AstrBot 提供安全的代码执行环境，**专为 Skill 执行设计**。

## 核心特性

### 🎯 专为 Skill 执行设计

- **LLM 工具集成** - 作为函数工具供 AI 直接调用
- **图片文件发送** - 支持从沙箱发送图片和文件到会话
- **多步骤操作** - 同一会话内文件持久化，支持复杂工作流
  - ⚠️ 注意：每次调用是新进程，环境变量和工作目录不保持
  - 多步骤命令需写成一行：`cd dir && python script.py`

### 🔒 多会话隔离

- **独立沙箱** - 每个会话拥有独立的 `/workspace` 目录
- **自动管理** - 会话结束后自动销毁，确保会话间完全隔离
- **安全隔离** - 文件系统、进程、用户权限全面隔离

### 🚀 复用宿主软件

- **零安装开销** - 直接使用宿主容器的 Python、Node.js、Git 等
- **全局包可用** - pip/npm 全局安装的包沙箱内直接可用
- **架构简洁** - 无需维护独立的 chroot 环境

### ⚡ 资源限制

- **内存限制** - 支持 Cgroup V2 物理内存限制
- **CPU 限制** - CPU 使用率和核数限制
- **进程限制** - 防止 fork 炸弹
- **时间限制** - 执行超时自动终止

### 💾 跨会话持久化数据

- **共享数据目录** - `/data` 目录跨会话持久化
- **技能目录** - `/skills` 目录可调用已安装的技能脚本
- **权限控制** - 支持按用户角色控制写入权限

## 快速开始

### LLM 工具调用

插件注册了 3 个 LLM 工具：

**execute_shell** - 执行 shell 命令
```python
execute_shell(command="python3 -c 'print(1+1)'", timeout=30)
```

**send_sandbox_image** - 发送沙箱内的图片
```python
send_sandbox_image(image_path="/workspace/chart.png")
```

**send_sandbox_file** - 发送沙箱内的文件
```python
send_sandbox_file(file_path="/workspace/report.txt")
```

### 命令调用

```
/nsjail python3 script.py
/nsjail ls /workspace
```

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| max_timeout | int | 60 | 最大执行超时（秒） |
| enable_network | bool | false | 是否允许网络访问 |
| memory_limit_mb | int | -1 | 内存限制（MB），-1 不限制 |
| cpu_limit_percent | int | -1 | CPU 限制（%），-1 不限制 |
| cpu_cores_limit | int | -1 | CPU 核数限制，-1 不限制 |
| process_limit | int | 50 | 进程数限制 |
| data_write_permission | string | "none" | /data 写权限（all/admin/none） |
| skills_write_permission | string | "none" | /skills 写权限（all/admin/none） |
| path | list | [默认PATH] | PATH 环境变量 |
| custom_env | list | [] | 自定义环境变量（KEY=VALUE） |

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
      - /sys/fs/cgroup:/sys/fs/cgroup:rw  # Cgroup V2 支持
    cap_add:
      - SYS_ADMIN  # 必需：挂载命名空间
      - NET_ADMIN  # 必需：网络命名空间
    security_opt:
      - apparmor=unconfined
      - seccomp=unconfined
    environment:
      - TZ=Asia/Shanghai
```

**关键配置**：
- `cap_add: [SYS_ADMIN, NET_ADMIN]` - 必需权限
- `/sys/fs/cgroup` - Cgroup V2 资源限制支持
- 不需要 `privileged: true`

## 沙箱目录结构

```
沙箱内视图：
/workspace/              # 当前会话工作目录（可读写）
/data/                   # 跨会话共享数据（权限可配置）
/AstrBot/data/skills/    # 技能目录（权限可配置）
/tmp/                    # 临时文件（会话独立）
/usr/, /bin/, /lib/      # 系统工具（只读，复用宿主）
~/.agents/skills/        # 符号链接到 /AstrBot/data/skills
```

**数据持久化**：
- `/workspace` - 会话结束后销毁
- `/data` - 永久保存，跨会话共享
- `/tmp` - 会话独立，会话结束后销毁

## 技术实现

### 隔离机制

| 隔离层级 | 实现方式 | 效果 |
|---------|---------|------|
| 文件系统 | Mount namespace + bindmount | 只能访问挂载的目录 |
| 进程 | PID namespace | 无法看到其他进程 |
| 网络 | Network namespace | 默认断网，可选启用 |
| 资源 | Cgroup V2 + rlimit | 内存/CPU/进程限制 |
| 用户 | UID 99999 | 非 root 运行 |

### 软件复用原理

通过 bindmount 只读挂载宿主目录：
```bash
--bindmount /usr:/usr:ro
--bindmount /bin:/bin:ro
--bindmount /lib:/lib:ro
```

**优势**：
- 无需维护独立的 chroot 环境
- 宿主安装软件，沙箱立即可用
- 节省磁盘空间（移除了 1.2GB 的 chroot）

## 预装软件

沙箱完全复用宿主容器的软件：
- Python 3.12+
- Node.js 24+
- Git, curl, wget
- 所有已安装的 Python 包和 npm 全局包

### 添加软件

**方式1：临时添加到 Docker 容器**
```bash
# 安装 Python 包
docker exec astrbot pip install requests pandas

# 安装 npm 全局包
docker exec astrbot npm install -g typescript

# 安装系统工具
docker exec astrbot apt-get update && apt-get install -y imagemagick
```
⚠️ 注意：容器重启后会丢失，适合临时测试。

**方式2：自行构建 Docker 镜像**
```dockerfile
FROM ghcr.io/ssttkkl/astrbot-plugin-nsjail:main

# 安装额外的 Python 包
RUN pip install requests pandas numpy

# 安装额外的 npm 包
RUN npm install -g typescript ts-node

# 安装系统工具
RUN apt-get update && apt-get install -y imagemagick ffmpeg
```

构建并使用：
```bash
docker build -t my-astrbot .
# 在 docker-compose.yml 中使用 image: my-astrbot
```

## 常见问题

### Q: 为什么需要 SYS_ADMIN 权限？

A: nsjail 的挂载命名空间需要此权限。相比 privileged 模式更安全。

### Q: 如何持久化数据？

A: 使用 `/data` 目录。例如：
```bash
# 保存配置
echo "key=value" > /data/myapp/config.txt

# 下次会话读取
cat /data/myapp/config.txt
```

### Q: 沙箱能访问网络吗？

A: 默认断网。设置 `enable_network: true` 启用网络。

### Q: 如何发送图片到会话？

A: 使用 `send_sandbox_image` 工具：
```python
# 1. 生成图片
execute_shell("python3 plot.py")  # 生成 chart.png

# 2. 发送图片
send_sandbox_image("/workspace/chart.png")
```

## 测试结果

### 自动化测试

**总体通过率：97.8% (138/141)**

| 类别 | 通过率 | 说明 |
|------|--------|------|
| 文件操作 | 100% (20/20) | ✅ 完全通过 |
| Node.js | 100% (17/17) | ✅ 完全通过 |
| Python | 100% (34/34) | ✅ 完全通过 |
| 安全与资源 | 100% (8/8) | ✅ 完全通过 |
| Shell | 97.5% (39/40) | ⚠️ 1个工具缺失 |
| 网络 | 85% (17/20) | ⚠️ 默认断网 |

详见 `agent-test/TEST_FAILURES.md`

### LLM 集成场景验证

针对 LLM Agent 实际使用场景的验证：

| 场景 | 结果 | 说明 |
|------|------|------|
| Shell 命令执行 | ✅ | 基础命令、管道、重定向正常 |
| Python 脚本 | ✅ | 标准库、第三方包可用 |
| Node.js 执行 | ✅ | npm 全局包可用 |
| 文件读写 | ✅ | /workspace 持久化正常 |
| SQLite 数据库 | ✅ | 文件锁正常，无 database locked 错误 |
| 网络访问 | ✅ | SSL 证书、DNS 配置正确 |
| 状态保持 | ⚠️ | 环境变量和工作目录不保持（已文档化） |
| 文件大小限制 | ✅ | rlimit_fsize 100MB 正确生效 |
| 超时控制 | ✅ | time_limit 精准终止长时间任务 |

## 已知限制

### Playwright / Chromium 不兼容

Chromium 在 nsjail 中会触发 SIGTRAP 崩溃。

**替代方案**：
- 使用 requests + BeautifulSoup
- 使用 curl/wget + 解析工具

## 相关链接

- [GitHub Repository](https://github.com/ssttkkl/astrbot-plugin-nsjail)
- [NsJail](https://github.com/google/nsjail)
- [AstrBot](https://github.com/Soulter/AstrBot)

## 许可证

MIT License
