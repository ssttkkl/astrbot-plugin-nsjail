# AstrBot NsJail 测试修复团队

## 团队目标
修复 astrbot-plugin-nsjail 的 23 个测试失败用例，提升通过率从 83.5% 到 >95%

## 团队角色

### 1. Orchestrator（你 - 主 Agent）
**职责**：
- 路由任务到合适的 agent
- 跟踪修复进度
- 决定优先级
- 汇总测试结果

**模型**：Claude Sonnet 4.6（当前模型）

---

### 2. Test Executor
**职责**：
- 执行测试脚本
- 分析测试结果
- 报告失败用例

**工作流程**：
```bash
1. SSH 端口转发到服务器
2. 执行 test-script.py <category>.json
3. 读取 test-results.json
4. 语义判断真实通过率
5. 报告失败用例和原因
```

**输出**：
- 通过率统计
- 失败用例列表（名称、预期、实际、原因）

**模型**：Claude（ACP）

---

### 3. Developer
**职责**：
- 根据测试反馈修复代码
- 只修改本地仓库代码
- 提交 git commit

**工作流程**：
```bash
1. 读取测试失败报告
2. 分析失败原因
3. 修改 sandbox_manager.py 或 main.py
4. 提交到 feature/fix_test_failure 分支
```

**约束**：
- 不在服务器上修改代码
- 不构建 Docker 镜像
- 每次只修复一个类别的问题

**模型**：Claude（ACP）

---

### 4. Code Reviewer
**职责**：
- 审查代码修改
- 检查安全性和正确性
- 决定是否需要返工

**审查清单**：
- [ ] 代码符合 Python 规范
- [ ] 修复逻辑正确
- [ ] 没有引入新的安全问题
- [ ] 没有破坏现有功能

**输出**：
- 通过/需要修改
- 具体问题列表（如果需要修改）

**模型**：Claude（ACP）

---

### 5. Deployer
**职责**：
- 部署代码到服务器
- 重启容器
- 验证服务正常

**工作流程**：
```bash
1. 推送代码到 GitHub
2. SSH 到服务器
3. git pull
4. docker restart astrbot
5. 验证服务启动
```

**模型**：Claude（ACP）

---

## 任务生命周期

```
Inbox → Assigned → In Progress → Review → Deploy → Test → Done | Failed
```

**状态定义**：
- **Inbox**：待修复的失败类别
- **Assigned**：分配给 Developer
- **In Progress**：Developer 正在修复
- **Review**：Code Reviewer 审查中
- **Deploy**：Deployer 部署到服务器
- **Test**：Test Executor 重新测试
- **Done**：测试通过
- **Failed**：测试仍失败，返回 In Progress

---

## 工作空间

```
~/.openclaw/workspace/astrbot-plugin-nsjail/
├── sandbox_manager.py          # 主要修改文件
├── main.py                     # 插件入口
├── agent-test/                 # 测试目录
│   ├── test-cases-*.json       # 测试用例
│   ├── test-script.py          # 测试脚本
│   ├── test-results.json       # 测试结果
│   └── TEST_FAILURES.md        # 失败报告
└── team/                       # 团队工作区（新建）
    ├── tasks/                  # 任务跟踪
    │   ├── task-001-security.md
    │   ├── task-002-shell-tools.md
    │   └── ...
    ├── reviews/                # 审查记录
    └── decisions/              # 决策记录
```

---

## 修复优先级

### P0 - 高优先级（安全问题）
1. 根目录未隔离
2. /proc 未隔离
3. fork 炸弹无限制
4. 环境变量未隔离

### P1 - 中优先级（功能缺失）
5. Shell 工具缺失（awk、which、xxd）
6. 网络工具缺失（nslookup、ping、wget、nc）
7. Python venv 支持

### P2 - 低优先级（测试用例问题）
8. Shell case 语句
9. Node.js 模板字符串

---

## 交接协议

### Developer → Code Reviewer
```markdown
**Commit Hash**: <hash>

**修改内容**：
- 文件：sandbox_manager.py
- 行数：L123-L125
- 变更：添加 --rlimit_nproc 50

**测试方法**：
cd agent-test && python3 test-script.py test-cases-安全.json

**已知问题**：
无

**下一步**：
审查安全性和正确性
```

### Code Reviewer → Deployer
```markdown
**审查结果**：通过
**Commit Hash**: <hash>（必须与 Developer 提供的一致）

**部署步骤**：
1. git push origin feature/fix_test_failure
2. SSH 到服务器
3. cd /opt/astrbot/data/plugins/astrbot_plugin_nsjail
4. git pull
5. **验证 commit hash**：git log -1 --oneline（必须匹配）
6. docker restart astrbot

**验证方法**：
docker logs astrbot | tail -20
```

### Deployer → Test Executor
```markdown
**部署完成**：
**Commit Hash**: <hash>（必须与 Code Reviewer 提供的一致）
- 分支：feature/fix_test_failure
- Commit：88c29e6
- 服务状态：运行中

**测试类别**：
安全测试（test-cases-安全.json）

**预期改善**：
fork 炸弹测试应该通过
```

---

## 迭代流程

```
第 N 轮迭代：

1. Orchestrator：选择下一个优先级任务
2. Test Executor：执行当前测试，报告失败
3. Developer：修复代码，提交 commit
4. Code Reviewer：审查代码
   - 如果不通过 → 返回 Developer
5. Deployer：部署到服务器
6. Test Executor：重新测试
   - 如果失败 → 返回 Developer
   - 如果通过 → 标记 Done
7. Orchestrator：汇总结果，决定是否继续

最大迭代次数：5 轮/任务
```

---

## 成功标准

- 安全测试：8/8 通过（100%）
- Shell 测试：>38/40 通过（>95%）
- 网络测试：>15/20 通过（>75%）
- 总通过率：>130/139（>93.5%）

---

## 团队启动命令

```python
# Orchestrator 启动团队
tasks = [
    {"id": "task-001", "category": "安全", "priority": "P0"},
    {"id": "task-002", "category": "Shell", "priority": "P1"},
    {"id": "task-003", "category": "网络", "priority": "P1"},
]

for task in tasks:
    # 1. Test Executor
    test_result = spawn_test_executor(task['category'])
    
    if test_result['all_passed']:
        continue
    
    # 2. Developer
    spawn_developer(task, test_result['failures'])
    
    # 3. Code Reviewer
    review = spawn_code_reviewer(task)
    
    if not review['approved']:
        continue  # 返回 Developer
    
    # 4. Deployer
    spawn_deployer(task)
    
    # 5. Test Executor（重新测试）
    retest_result = spawn_test_executor(task['category'])
    
    # 6. 报告结果
    report_result(task, retest_result)
```
