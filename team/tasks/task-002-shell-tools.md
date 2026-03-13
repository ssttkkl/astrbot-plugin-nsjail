# Task 002 - Shell 工具缺失修复

**优先级**: P1（中）
**类别**: Shell
**状态**: Assigned
**创建时间**: 2026-03-14 00:53

## 失败用例（来自 TEST_FAILURES.md）

1. **awk 处理** - `awk: command not found`
2. **which 命令** - `which: command not found`
3. **十六进制转换** - `xxd: command not found`
4. **用户信息** - `whoami: cannot find name for user ID 99999`
5. **Shell case 语句** - 逻辑错误

## 修复方案

### 方案 A：在 Dockerfile 中安装工具
```dockerfile
RUN apt-get update && apt-get install -y \
    gawk \
    xxd \
    && rm -rf /var/lib/apt/lists/*
```

### 方案 B：创建 whoami 替代脚本
```bash
echo "sandbox-user" > /usr/local/bin/whoami
chmod +x /usr/local/bin/whoami
```

## 下一步

执行 Shell 测试，确认失败数量
