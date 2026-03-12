# AstrBot NsJail 插件测试失败用例汇总

**生成时间**: 2026-03-13 00:25  
**测试环境**: AstrBot nsjail 沙箱  
**总失败数**: 44个

---

## Python (6个失败)

### requests库-GET
- **输入**: HTTP GET 请求应该返回状态码 200
- **输出**: `Temporary failure in name resolution`
- **失败原因**: DNS 解析失败，沙箱环境网络隔离

### requests库-POST
- **输入**: POST 请求应该返回 JSON 中的 key 字段值 value
- **输出**: `Temporary failure in name resolution`
- **失败原因**: DNS 解析失败，沙箱环境网络隔离

### httpx同步请求
- **输入**: HTTP 请求应该返回状态码 200
- **输出**: 网络连接失败
- **失败原因**: 沙箱环境网络隔离

### aiohttp客户端
- **输入**: 异步 HTTP 请求应该返回状态码 200
- **输出**: DNS 解析失败
- **失败原因**: 沙箱环境网络隔离

### fastapi路由定义
- **输入**: 应该返回字典包含 Hello 键
- **输出**: `ModuleNotFoundError: No module named 'fastapi'`
- **失败原因**: 容器内未安装 fastapi 模块

### typer CLI
- **输入**: 应该输出 Hello World
- **输出**: `ModuleNotFoundError: No module named 'typer'`
- **失败原因**: 容器内未安装 typer 模块

---

## Shell (12个失败)

### awk处理
- **输入**: 应该提取第二列输出 2
- **输出**: `awk: command not found`
- **失败原因**: 容器内缺少 awk 命令

### which命令
- **输入**: 应该找到 python3 的路径
- **输出**: `which: command not found`
- **失败原因**: 容器内缺少 which 命令

### 用户信息
- **输入**: 应该显示当前用户名
- **输出**: `whoami: cannot find name for user ID 99999`
- **失败原因**: UID 99999 在容器内没有对应的用户名

### Shell函数定义
- **输入**: 应该定义函数并调用返回 10
- **输出**: 算术语法错误
- **失败原因**: Shell 算术表达式转义问题

### Shell数组操作
- **输入**: 应该访问数组元素返回 b
- **输出**: 数组语法未展开
- **失败原因**: Bash 数组语法在命令中未正确解析

### Shell关联数组
- **输入**: 应该访问关联数组返回 value
- **输出**: 关联数组语法未展开
- **失败原因**: Bash 关联数组语法在命令中未正确解析

### Shell字符串截取
- **输入**: 应该截取字符串返回 ell
- **输出**: 字符串截取语法未展开
- **失败原因**: Bash 字符串截取语法在命令中未正确解析

### Shell参数展开
- **输入**: 应该使用默认值返回 test
- **输出**: 参数展开语法未展开
- **失败原因**: Bash 参数展开语法在命令中未正确解析

### Shell进程替换
- **输入**: 应该比较两个命令输出，发现不同
- **输出**: `/dev/fd/63: No such file or directory`
- **失败原因**: /dev/fd 在沙箱中不可访问

### Shell算术运算
- **输入**: 应该计算表达式返回 70
- **输出**: 算术语法错误
- **失败原因**: 转义导致算术表达式解析失败

### 十六进制
- **输入**: 应该转换为十六进制 68656c6c6f
- **输出**: `xxd: command not found`
- **失败原因**: 容器内缺少 xxd 命令

---

## 网络 (9个失败)

### DNS解析-百度
- **输入**: 应该解析域名并返回 IP 地址
- **输出**: `nslookup: command not found`
- **失败原因**: 容器内缺少 nslookup 命令

### DNS解析-Google
- **输入**: 应该解析域名并返回 IP 地址
- **输出**: `nslookup: command not found`
- **失败原因**: 容器内缺少 nslookup 命令

### ping本地
- **输入**: 应该 ping 成功，显示发送和接收的包数
- **输出**: `ping: command not found`
- **失败原因**: 容器内缺少 ping 命令

### curl百度
- **输入**: 应该返回 HTTP 状态码 200 或 30x
- **输出**: 退出码 23，返回 301
- **失败原因**: curl 返回正确状态码但退出码 23 表示写入错误

### TCP连接测试
- **输入**: 应该尝试 TCP 连接
- **输出**: `nc: command not found`
- **失败原因**: 容器内缺少 nc (netcat) 命令

### UDP测试
- **输入**: 应该尝试 UDP 连接
- **输出**: `nc: command not found`
- **失败原因**: 容器内缺少 nc (netcat) 命令

### 下载速度测试
- **输入**: 应该显示下载速度
- **输出**: 退出码 23，速度为 0
- **失败原因**: curl 写入错误导致下载失败

### Node.js HTTP请求
- **输入**: 应该发送 HTTP 请求并返回状态码 200
- **输出**: `Fatal process out of memory: SegmentedTable::InitializeTable`
- **失败原因**: Node.js 进程内存不足，512MB 限制过低

### Node.js HTTPS请求
- **输入**: 应该发送 HTTPS 请求并返回状态码 200
- **输出**: `Fatal process out of memory: SegmentedTable::InitializeTable`
- **失败原因**: Node.js 进程内存不足，512MB 限制过低

---

## Node.js (16个失败)

所有 Node.js 测试（除版本查询外）均因相同原因失败：

### 通用失败模式
- **输入**: 执行任何 JavaScript 代码
- **输出**: `Fatal process out of memory: SegmentedTable::InitializeTable (subspace allocation)`, 退出码 133
- **失败原因**: Node.js V8 引擎初始化需要超过 512MB 内存，当前 nsjail 内存限制过低

**受影响的测试**:
- Node计算、数组、对象、字符串、JSON
- map、filter、reduce、箭头函数
- 模板字符串、解构、扩展运算符
- Promise、async/await、Set、Map

---

## 安全 (1个失败)

### Fork炸弹
- **输入**: 应该被进程数限制阻止
- **输出**: 虽然 /dev/null 被阻止，但进程仍能 fork
- **失败原因**: 缺少 `--rlimit_nproc` 限制，进程数未受控

---

## 失败原因统计

| 原因类别 | 数量 | 占比 |
|---------|------|------|
| 缺少命令工具 | 10 | 22.7% |
| Node.js 内存不足 | 16 | 36.4% |
| 网络隔离 | 4 | 9.1% |
| Shell 语法问题 | 6 | 13.6% |
| 缺少 Python 模块 | 2 | 4.5% |
| /dev 文件系统限制 | 2 | 4.5% |
| 其他 | 4 | 9.1% |

---

## 改进建议

### 1. 安装缺失工具
```bash
apt-get install -y \
  gawk \
  iputils-ping \
  dnsutils \
  net-tools \
  netcat-openbsd \
  xxd
```

### 2. 增加内存限制
```python
"--rlimit_as", "2048",  # 从 512MB 增加到 2048MB
```

### 3. 添加进程数限制
```python
"--rlimit_nproc", "50",  # 限制最大进程数
```

### 4. 安装 Python 模块
```bash
pip install fastapi typer
```

### 5. 修复 Shell 语法测试
- 使用文件方式而非命令行参数
- 避免复杂的转义和参数展开

---

## 结论

**核心功能正常**: 文件操作 (100%)、基础 Python (81%)、基础 Shell (75%)

**需要改进**: Node.js 支持、网络工具、高级 Shell 语法

**优先级**:
1. 高：增加内存限制（解决 Node.js 问题）
2. 中：安装网络诊断工具
3. 低：优化 Shell 语法测试用例
