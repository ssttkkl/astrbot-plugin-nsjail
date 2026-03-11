# AstrBot NsJail 沙箱插件

为 AstrBot 提供基于 NsJail 的安全代码执行环境，支持 LLM 函数调用。

## 功能特性

- 🔒 **完整文件系统隔离** - 使用 chroot 隔离，无法访问容器外文件
- 📦 **独立沙箱环境** - 每个会话拥有独立的工作目录
- ⚡ **资源限制** - CPU、内存、文件大小、执行时间全面限制
- 🔄 **自动管理** - 沙箱自动创建、复用和销毁
- 🤖 **LLM 集成** - 作为函数工具供 LLM 调用

## 技术方案

### 隔离架构

```
容器环境
├── /AstrBot/              # AstrBot 主程序（隔离）
│   └── data/skills/       # AstrBot 技能目录
├── /nsjail-root/          # 预构建的最小 Debian 系统
│   ├── bin/python3        # Python 解释器
│   ├── lib/               # 动态库
│   └── usr/               # 系统文件
└── /tmp/nsjail_xxx/       # 用户沙箱目录
    └── (挂载到沙箱内的 /workspace)
```

沙箱内目录结构：
```
/
├── workspace/              # 可读写，用户工作目录
├── AstrBot/data/skills/   # 只读，AstrBot 技能目录（与容器内相同路径）
└── tmp/                   # 独立 tmpfs，每次执行清空
```

### NsJail 配置

```bash
nsjail \
  --chroot /nsjail-root \              # 使用预构建根文件系统
  --bindmount /tmp/sandbox:/workspace \ # 挂载用户沙箱
  --cwd /workspace \                   # 工作目录
  --time_limit 30 \                    # 30秒超时
  --max_cpus 1 \                       # 1核CPU
  --rlimit_as 512 \                    # 512MB内存
  --rlimit_fsize 100 \                 # 100MB文件大小
  -- /bin/bash -c "command"
```

### 安全保障

| 隔离层级 | 实现方式 | 效果 |
|---------|---------|------|
| 文件系统 | chroot + 预构建 rootfs | 无法访问 /AstrBot、容器配置等 |
| 进程 | PID namespace | 无法看到其他进程 |
| 网络 | 默认隔离 | 可选启用网络访问 |
| 资源 | rlimit | CPU/内存/文件大小限制 |

## 部署方式

### Docker 镜像（推荐）

使用预构建的 Docker 镜像，包含 nsjail 和隔离环境：

```yaml
services:
  astrbot:
    image: ghcr.io/ssttkkl/astrbot-with-nsjail:latest
    privileged: true  # nsjail 需要
    volumes:
      - ./data:/AstrBot/data
```

### 手动安装

1. 安装 nsjail
2. 创建 chroot 环境
3. 安装插件

详见 [部署文档](./docs/deployment.md)

## 使用方法

### LLM 函数调用

插件会自动注册 `execute_shell` 函数工具，LLM 可以直接调用：

```
用户: 用代码计算 1+1
LLM: [调用 execute_shell("echo $((1+1))")]
结果: 2
```

### 配置

`data/config/astrbot_plugin_nsjail_config.json`:

```json
{
  "max_timeout": 60,
  "enable_network": false
}
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `max_timeout` | int | 60 | 最大执行超时时间（秒） |
| `enable_network` | bool | false | 是否允许沙箱访问网络。默认禁用以保证安全 |

## 资源限制

| 资源 | 默认限制 | 说明 |
|------|---------|------|
| 执行时间 | 30秒 | 可通过参数调整，最大 60 秒 |
| 内存 | 512MB | 超出会被 OOM kill |
| 文件大小 | 100MB | 单个文件最大 |
| CPU | 1核 | 限制 CPU 使用 |

## 预装软件

沙箱环境预装：
- Python 3
- Bash
- Coreutils (ls, cat, echo 等)

### 添加更多软件包

修改 `pkg/Dockerfile`:

```dockerfile
# 方法1: 系统包
RUN debootstrap --variant=minbase \
    --include=python3,python3-pip,python3-numpy,bash,curl \
    stable /nsjail-root http://deb.debian.org/debian

# 方法2: pip 包
RUN chroot /nsjail-root pip3 install pandas requests
```

## 常见问题

### Q: 为什么需要 privileged 模式？

A: nsjail 的 chroot 功能需要特权。虽然使用 privileged，但沙箱内的进程仍然被严格隔离。

### Q: 如何避免挂载权限问题？

A: 我们在镜像构建时预先创建 chroot 环境，运行时只需切换根目录，不涉及动态挂载。

### Q: 沙箱能访问网络吗？

A: 默认隔离网络。如需网络访问，可修改 nsjail 配置移除网络隔离。

## 开发

```bash
# 克隆仓库
git clone https://github.com/ssttkkl/astrbot-plugin-nsjail.git

# 构建镜像
docker build -t astrbot-with-nsjail ./pkg

# 测试
docker run -it astrbot-with-nsjail nsjail --version
```

## 许可证

MIT License

## 相关链接

- [NsJail](https://github.com/google/nsjail)
- [AstrBot](https://github.com/Soulter/AstrBot)
- [Docker 镜像](https://github.com/ssttkkl/astrbot-plugin-nsjail/pkgs/container/astrbot-with-nsjail)
