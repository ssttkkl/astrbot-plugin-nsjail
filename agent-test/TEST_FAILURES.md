# AstrBot NsJail 插件测试失败用例汇总

**生成时间**: 2026-03-13 22:37  
**测试环境**: AstrBot nsjail 沙箱  
**总失败数**: 23个

---

## Python (2个失败)

### 创建venv并安装包
- **输入**: 创建虚拟环境并安装包
- **输出**: `Error: Command '['/workspace/venv/bin/python3', '-m', 'ensurepip']' returned non-zero exit status 1.`
- **失败原因**: Python 3.13 缺少 ensurepip 模块，无法创建虚拟环境

### venv中运行脚本
- **输入**: 在虚拟环境中运行脚本
- **输出**: venv 创建失败，但脚本仍执行并输出 "hello from venv"
- **失败原因**: 虚拟环境创建失败（同上）

---

## Shell (5个失败)

### awk处理
- **输入**: 应该提取第二列输出 2
- **输出**: `awk: command not found`, 退出码 127
- **失败原因**: 容器内缺少 awk 命令

### which命令
- **输入**: 应该找到 python3 的路径
- **输出**: `which: command not found`, 退出码 127
- **失败原因**: 容器内缺少 which 命令

### 用户信息
- **输入**: 应该显示当前用户名
- **输出**: `whoami: cannot find name for user ID 99999`, 退出码 1
- **失败原因**: UID 99999 在容器内没有对应的用户名

### Shell case语句
- **输入**: 应该输出 "two"
- **输出**: 空输出
- **失败原因**: case 语句逻辑错误或变量未正确传递

### 十六进制
- **输入**: 应该转换为十六进制 68656c6c6f
- **输出**: `xxd: command not found`, 退出码 127
- **失败原因**: 容器内缺少 xxd 命令

---

## 网络 (12个失败)

### DNS解析-百度
- **输入**: 应该解析域名并返回 IP 地址
- **输出**: `nslookup: command not found`, 退出码 127
- **失败原因**: 容器内缺少 nslookup 命令

### DNS解析-Google
- **输入**: 应该解析域名并返回 IP 地址
- **输出**: `nslookup: command not found`, 退出码 127
- **失败原因**: 容器内缺少 nslookup 命令

### ping本地
- **输入**: 应该 ping 成功，显示发送和接收的包数
- **输出**: `ping: command not found`, 退出码 127
- **失败原因**: 容器内缺少 ping 命令

### wget测试
- **输入**: 应该下载文件
- **输出**: `wget: command not found`, 退出码 127
- **失败原因**: 容器内缺少 wget 命令

### netcat监听
- **输入**: 应该启动 netcat 监听
- **输出**: `nc: command not found`, 退出码 127
- **失败原因**: 容器内缺少 nc (netcat) 命令

### telnet测试
- **输入**: 应该测试 telnet 连接
- **输出**: `telnet: command not found`, 退出码 127
- **失败原因**: 容器内缺少 telnet 命令

### Node.js HTTP请求
- **输入**: 应该发送 HTTP 请求并返回状态码 200
- **输出**: 进程被杀死，退出码 137
- **失败原因**: 超时或内存限制

### Node.js HTTPS请求
- **输入**: 应该发送 HTTPS 请求并返回状态码 200
- **输出**: `unable to verify the first certificate`
- **失败原因**: SSL 证书验证失败

### 检查网络接口
- **输入**: 应该显示网络接口信息
- **输出**: `ip: command not found` 和 `ifconfig: command not found`, 退出码 127
- **失败原因**: 容器内缺少 ip 和 ifconfig 命令

### 检查路由表
- **输入**: 应该显示路由表
- **输出**: `ip: command not found` 和 `route: command not found`, 退出码 127
- **失败原因**: 容器内缺少 ip 和 route 命令

### TCP连接测试
- **输入**: 应该尝试 TCP 连接
- **输出**: `nc: command not found`, 退出码 127
- **失败原因**: 容器内缺少 nc (netcat) 命令

### UDP测试
- **输入**: 应该尝试 UDP 连接
- **输出**: `nc: command not found`, 退出码 127
- **失败原因**: 容器内缺少 nc (netcat) 命令

---

## Node.js (1个失败)

### Node模板字符串
- **输入**: 应该输出 "HELLO"
- **输出**: `x=5`
- **失败原因**: 测试用例逻辑错误或变量未正确传递

---

## 安全 (1个失败)

### 尝试fork炸弹
- **输入**: 应该被限制或超时
- **输出**: 成功执行并输出 `done`
- **失败原因**: 进程数限制不够严格，缺少 `--rlimit_nproc` 限制


---

## 失败原因统计

| 原因类别 | 数量 | 占比 |
|---------|------|------|
| 缺少命令工具 | 12 | 52.2% |
| 安全隔离不足 | 4 | 17.4% |
| Python venv 问题 | 2 | 8.7% |
| Shell 语法/逻辑 | 2 | 8.7% |
| Node.js 问题 | 2 | 8.7% |
| 其他 | 1 | 4.3% |

---

## 改进建议

### 1. 安装缺失工具（高优先级）
```bash
apt-get install -y \
  gawk \
  iputils-ping \
  dnsutils \
  net-tools \
  netcat-openbsd \
  xxd \
  wget \
  telnet \
  iproute2
```

### 2. 加强安全隔离（高优先级）
```python
# 添加进程数限制
"--rlimit_nproc", "50",

# 考虑使用 chroot 或更严格的文件系统隔离
# 限制 /proc 访问范围
```

### 3. 修复 Python venv 问题（中优先级）
```bash
# 安装 python3-venv 包
apt-get install -y python3.13-venv
```

### 4. 优化 Node.js 支持（中优先级）
- 检查 SSL 证书配置
- 优化内存使用或增加限制

### 5. 修复测试用例（低优先级）
- Shell case 语句测试
- Node.js 模板字符串测试

---

## 测试通过率汇总

| 测试类别 | 通过/总数 | 通过率 |
|---------|----------|--------|
| 文件操作 | 20/20 | 100% |
| Python | 33/35 | 94.3% |
| Node.js | 16/17 | 94.1% |
| Shell | 35/40 | 87.5% |
| 安全 | 4/8 | 50% |
| 网络 | 8/20 | 40% |
| **总计** | **116/139** | **83.5%** |

---

## 结论

**核心功能正常**: 文件操作 (100%)、Python (94.3%)、Node.js (94.1%)、Shell (87.5%)

**安全问题**: 
- 🔴 高风险：根目录和 /proc 未隔离
- 🟡 中风险：fork 炸弹无限制
- 🟡 中风险：环境变量未隔离

**功能缺失**: 
- 网络诊断工具（nslookup、ping、wget、nc 等）
- Shell 工具（awk、which、xxd）
- Python venv 支持

**优先级**:
1. 🔴 高：加强安全隔离（根目录、/proc、进程数）
2. 🟡 中：安装网络和 Shell 工具
3. 🟢 低：修复 Python venv 和测试用例
