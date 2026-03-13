#!/bin/bash
# 重新测试所有类别

cd /Users/huangwenlong/.openclaw/workspace/astrbot-plugin-nsjail/agent-test

echo "开始重新测试..."

# 测试 Shell
echo "测试 Shell..."
python3 test-script.py test-cases-shell.json astrbot d57e17c796fe1a89cd2ccac987f1531b
mv test-results.json test-results-shell.json

# 测试网络
echo "测试网络..."
python3 test-script.py test-cases-网络.json astrbot d57e17c796fe1a89cd2ccac987f1531b
mv test-results.json test-results-network.json

echo "测试完成！"
