# AstrBot NsJail 插件测试指南

## 测试环境

**⚠️ 敏感信息（服务器地址、密码等）请查看 `SECRET.md` 文件**

**插件路径**: /opt/astrbot/data/plugins/astrbot_plugin_nsjail/

## 测试用例分类

本目录包含以下测试用例集：

| 文件 | 数量 | 说明 |
|------|------|------|
| `test-cases-python.json` | 35 | Python 三方库和系统调用 |
| `test-cases-shell.json` | 47 | Shell 脚本、系统能力、编码、计算、文本处理 |
| `test-cases-node.js.json` | 17 | Node.js 功能（需更大内存） |
| `test-cases-文件.json` | 20 | 文件操作和权限 |
| `test-cases-网络.json` | 20 | 网络请求和连接（需启用网络） |

**总计**: 139 个测试用例

## 测试脚本

### test-script.py

执行测试并输出原始结果，由 agent 读取并进行语义判断。

**用法**:
```bash
python3 test-script.py <test-cases.json> <username> <password_md5>
```

**示例**:
```bash
python3 test-script.py test-cases-python.json astrbot d57e17c796fe1a89cd2ccac987f1531b
```

**输出**:
- 测试结果保存到 `test-results.json`
- 包含每个测试的完整输出（前 500 字符）
- Agent 需要读取此文件并根据语义判断测试是否真正通过

## 执行测试的提示词

当需要执行测试时，使用以下提示词：

---

### 提示词模板

详见 `SECRET.md`（敏感信息）

基本流程：
1. 建立 SSH 端口转发
2. 进入测试目录
3. 执行 test-script.py
4. 读取 test-results.json 文件
5. 根据语义判断每个测试是否真正通过（不要只看 passed 字段）
6. 分析失败原因并生成报告

测试分类选项：
- python (35个) - Python 三方库和系统调用
- shell (47个) - Shell 脚本、系统能力、编码、计算、文本处理
- 文件 (20个) - 文件操作
- 网络 (20个) - 网络功能（需启用 enable_network）
- node.js (17个) - Node.js（需增加内存限制）

---

### Agent 判断逻辑

读取 `test-results.json` 后，对每个测试：

1. **查看测试用例**：理解测试的目的和预期结果
2. **分析实际输出**：检查输出内容是否符合预期
3. **语义判断**：
   - 输出格式可能不同，但语义正确 → 通过
   - 包含错误信息或异常 → 失败
   - 退出码非 0 且不符合预期 → 失败
4. **记录真实结果**：更新通过/失败状态

**示例**：
- 测试预期 "200"，输出 "退出码: 0\n输出:\n200" → 通过
- 测试预期 "hello"，输出 "HELLO" → 需根据测试意图判断
- 输出包含 "Error" 或 "Failed" → 通常是失败

---

### 完整测试流程

```
执行 astrbot-plugin-nsjail 的完整测试流程：

1. 建立 SSH 端口转发
2. 依次测试各个分类：
   - Python 测试 (35个)
   - Shell 测试 (47个)
   - 文件操作测试 (20个)
   - 网络测试 (20个)
   - Node.js 测试 (17个)
3. 对每个分类：
   a. 执行 test-script.py
   b. 读取 test-results.json
   c. 语义判断真实通过率
   d. 分析失败原因
4. 汇总所有测试结果
5. 生成完整测试报告
```

---

## 测试注意事项

### 内存限制

当前配置：`--rlimit_as 512` (512MB)

**影响**：
- Node.js 测试会因 OOM 失败
- 建议增加到 1024MB 或 2048MB

### 网络测试

网络测试需要启用网络访问：

**配置文件**: `/opt/astrbot/data/config/astrbot_plugin_nsjail_config.json`
```json
{
  "enable_network": true
}
```

### 已知问题

1. **Node.js OOM**: 512MB 内存不足，需要增加限制
2. **命令缺失**: `which`, `ps`, `xxd` 等命令在容器中不存在
3. **环境变量**: nsjail 可能清空部分环境变量

## 测试结果分析

测试完成后，检查：
1. 通过率是否符合预期（目标 >90%）
2. 失败用例的原因分类
3. 是否需要调整配置或测试用例

## 持续集成

建议将测试集成到 CI/CD 流程：
1. 代码提交后自动运行测试
2. 测试失败时阻止部署
3. 定期运行完整测试套件
