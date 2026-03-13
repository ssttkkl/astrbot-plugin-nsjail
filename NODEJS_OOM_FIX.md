# Node.js OOM 问题修复方案

## 问题分析

**现象**：
- Node.js HTTP 请求成功完成（输出 200）
- 进程随后被 OOM killer 杀死（exit code 137）

**原因**：
- 当前配置 `memory_limit_mb = -1`（不限制内存）
- Node.js V8 引擎可能消耗大量内存
- 触发系统级 OOM killer

## 解决方案

### 方案 1：启用 Cgroup V2 内存限制（推荐）

通过 AstrBot Dashboard 配置插件：

1. 访问 Dashboard：http://服务器IP:6185
2. 进入"插件管理" → "astrbot_plugin_nsjail"
3. 修改配置：
   - `memory_limit_mb`: 256（推荐值，可根据需求调整）
   - `cpu_limit_percent`: 50（可选，限制 CPU 使用）

**推荐配置**：
```json
{
  "max_timeout": 60,
  "enable_network": false,
  "memory_limit_mb": 256,
  "cpu_limit_percent": -1
}
```

### 方案 2：通过 API 配置

```bash
# 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:6185/api/v1/dashboard/login \
  -H "Content-Type: application/json" \
  -d '{"username":"astrbot","password":"d57e17c796fe1a89cd2ccac987f1531b"}' \
  | jq -r '.data.token')

# 更新插件配置
curl -X POST http://localhost:6185/api/v1/dashboard/plugin/nsjail/config \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "max_timeout": 60,
    "enable_network": false,
    "memory_limit_mb": 256,
    "cpu_limit_percent": -1
  }'
```

## 内存限制建议

| 场景 | 推荐值 | 说明 |
|------|--------|------|
| 轻量脚本 | 128 MB | Python/Shell 简单任务 |
| Node.js 基础 | 256 MB | HTTP 请求、简单计算 |
| Node.js 复杂 | 512 MB | 数据处理、复杂逻辑 |
| 不限制 | -1 | 仅用于调试，生产环境不推荐 |

## 验证

配置后重新测试：
```bash
/nsjail node -e 'require("http").get("http://example.com",r=>console.log(r.statusCode))'
```

预期结果：
- 退出码：0（成功）
- 输出：200
- 无 OOM 错误

## 注意事项

1. **Cgroup V2 要求**：
   - Docker 需要挂载 `/sys/fs/cgroup:/sys/fs/cgroup:rw`
   - 容器需要 `SYS_ADMIN` capability

2. **内存不足时的行为**：
   - 进程会被 nsjail 的 Cgroup 限制杀死
   - 退出码：137（SIGKILL）
   - 不会影响宿主系统

3. **调试建议**：
   - 先设置较大值（512 MB）验证功能
   - 逐步降低找到最优值
   - 监控实际内存使用情况
