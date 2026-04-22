#!/usr/bin/env python3
"""
AstrBot 插件测试脚本

使用前需要：
1. 设置 SSH 端口转发：ssh -fNL 6185:127.0.0.1:6185 root@<服务器IP>
2. 从 AstrBot 配置文件获取用户名和密码：
   - 配置文件路径：${ASTRBOT_DIR}/data/config.yaml
   - 查找 dashboard_username 和 dashboard_password
   - 密码已经是 MD5 哈希值，直接使用
"""
import asyncio
import json
import sys
import hashlib
import aiohttp

API_BASE = "http://127.0.0.1:6185/api"

async def login(session: aiohttp.ClientSession, username, password_md5):
    """登录获取 token"""
    async with session.post(
        f"{API_BASE}/auth/login",
        json={"username": username, "password": password_md5},
        timeout=aiohttp.ClientTimeout(total=10)
    ) as response:
        data = await response.json()
    if data.get('status') == 'ok' and 'data' in data and 'token' in data['data']:
        return data['data']['token']
    else:
        raise Exception(f"登录失败: {data}")

async def run_test(session: aiohttp.ClientSession, test_case, session_id, token):
    """执行单个测试，支持多步骤命令"""
    if 'commands' in test_case:
        commands = test_case['commands']
    else:
        commands = [test_case['command']]
    if isinstance(commands, str):
        commands = [commands]

    all_output = ""
    for cmd in commands:
        async with session.post(
            f"{API_BASE}/chat/send",
            headers={'Authorization': f'Bearer {token}'},
            json={'message': cmd, 'session_id': session_id},
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            output = ""
            async for line in response.content:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'plain':
                            output += data.get('data', '')
                        elif data.get('type') == 'end':
                            break
                    except json.JSONDecodeError:
                        pass

        all_output += output + "\n---\n"
        await asyncio.sleep(0.5)  # 等待沙箱状态更新

    return {
        'name': test_case['name'],
        'expected': test_case['expected'],
        'output': all_output[:1000],
        'category': test_case.get('category', 'Unknown')
    }

async def main():
    if len(sys.argv) < 4:
        print("用法: python3 test-script.py <test-cases.json> <username> <password_md5>")
        print("从 AstrBot 配置文件获取用户名和密码：${ASTRBOT_DIR}/data/config.yaml")
        sys.exit(1)

    username = sys.argv[2]
    password_md5 = sys.argv[3]

    async with aiohttp.ClientSession() as session:
        token = await login(session, username, password_md5)
        print(f"✓ 登录成功，获取 token")

        with open(sys.argv[1], encoding='utf-8') as f:
            tests = json.load(f)

        results = [await run_test(session, t, f"test-{i}", token) for i, t in enumerate(tests)]

    with open('test-results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✓ 测试完成，结果保存到 test-results.json")

if __name__ == '__main__':
    asyncio.run(main())
