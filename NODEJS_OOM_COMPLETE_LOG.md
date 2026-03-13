# Node.js OOM 完整日志

## 测试环境
- 时间：2026-03-14 02:45-03:09
- 服务器：123.57.192.94
- 容器：astrbot
- Node.js 版本：v24.14.0

## Node.js HTTP 请求测试

**命令**：
```bash
node -e 'require("http").get("http://example.com",r=>console.log(r.statusCode))'
```

**nsjail 完整命令**：
```bash
nsjail --mode o --user 99999 --group 99999 \
  --disable_clone_newuser \
  --bindmount /tmp/nsjail_webchat_astrbot_test-10_1773427491_rfzadjm7:/workspace:rw \
  --bindmount /usr:/usr:ro \
  --bindmount /lib:/lib:ro \
  --bindmount /lib64:/lib64:ro \
  --bindmount /bin:/bin:ro \
  --bindmount /sbin:/sbin:ro \
  --bindmount /etc/alternatives:/etc/alternatives:ro \
  --bindmount /tmp:/tmp:rw \
  --bindmount /sandbox-cache:/sandbox-cache:rw \
  --bindmount /dev/null:/dev/null:rw \
  --bindmount /dev/urandom:/dev/urandom:ro \
  --disable_clone_newnet \
  --bindmount /etc/resolv.conf:/etc/resolv.conf:ro \
  --bindmount /etc/ssl:/etc/ssl:ro \
  --bindmount /AstrBot/data/skills:/AstrBot/data/skills:ro \
  --cwd /workspace \
  --time_limit 30 \
  --rlimit_fsize 100 \
  --rlimit_nproc 50 \
  --env PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin \
  --env UV_CACHE_DIR=/sandbox-cache/uv \
  --env HOME=/workspace \
  --quiet \
  -- /bin/bash -c "node -e 'require(\"http\").get(\"http://example.com\",r=>console.log(r.statusCode))'"
```

**结果**：
```
退出码: 137
输出:
200
```

**分析**：
- HTTP 请求成功完成（输出 200）
- 进程随后被 OOM killer 杀死（exit code 137 = SIGKILL）
- 当前配置没有内存限制（`memory_limit_mb = -1`）

---

## Node.js HTTPS 请求测试

**命令**：
```bash
node -e 'require("https").get("https://example.com",r=>console.log(r.statusCode))'
```

**结果**：
```
退出码: 1
输出:
node:events:486
      throw er; // Unhandled 'error' event
      ^

Error: unable to get local issuer certificate
    at TLSSocket.onConnectSecure (node:internal/tls/wrap:1649:34)
    at TLSSocket.emit (node:events:508:28)
    at TLSSocket._finishInit (node:internal/tls/wrap:1095:8)
    at ssl.onhandshakedone (node:internal/tls/wrap:881:12)
Emitted 'error' event on ClientRequest instance at:
    at emitErrorEvent (node:_http_client:108:11)
    at TLSSocket.socketErrorListener (node:_http_client:575:5)
    at TLSSocket.emit (node:events:508:28)
    at emitErrorNT (node:internal/streams/destroy:170:8)
    at emitErrorCloseNT (node:internal/streams/destroy:129:3)
    at process.processTicksAndRejections (node:internal/process/task_queues:90:21) {
  code: 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY'
}

Node.js v24.14.0
```

**分析**：
- SSL 证书验证失败
- `/etc/ssl/certs` 是符号链接，指向 `/etc/pki/tls/certs`（CentOS/RHEL）或 `/etc/ca-certificates`（Debian/Ubuntu）
- 需要挂载真实的证书路径

---

## 解决方案

### 1. OOM 问题（exit 137）
启用 Cgroup V2 内存限制：
```json
{
  "memory_limit_mb": 256
}
```

### 2. SSL 证书问题
已修复（commit 066994d）：
- 条件挂载 `/etc/pki`（CentOS/RHEL）
- 条件挂载 `/etc/ca-certificates`（Debian/Ubuntu）

---

**生成时间**：2026-03-14 03:10
