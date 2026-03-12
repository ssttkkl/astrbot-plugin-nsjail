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
import json, sys, requests, time, hashlib

API_BASE = "http://127.0.0.1:6185/api"

def login(username, password_md5):
    """登录获取 token"""
    response = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": username, "password": password_md5},
        timeout=10
    )
    data = response.json()
    if data.get('status') == 'ok' and 'data' in data and 'token' in data['data']:
        return data['data']['token']
    else:
        raise Exception(f"登录失败: {data}")

def run_test(test_case, session_id, token):
    message = test_case['command']
    response = requests.post(
        f"{API_BASE}/chat/send",
        headers={'Authorization': f'Bearer {token}'},
        json={'message': message, 'session_id': session_id},
        stream=True,
        timeout=60
    )
    
    output = ""
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                try:
                    data = json.loads(line_str[6:])
                    if data.get('type') == 'plain':
                        output += data.get('data', '')
                    elif data.get('type') == 'end':
                        break
                except:
                    pass
    
    return {
        'name': test_case['name'],
        'expected': test_case['expected'],
        'output': output[:500],
        'category': test_case.get('category', 'Unknown')
    }

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("用法: python3 test-script.py <test-cases.json> <username> <password_md5>")
        print("从 AstrBot 配置文件获取用户名和密码：${ASTRBOT_DIR}/data/config.yaml")
        sys.exit(1)
    
    # 登录获取 token
    username = sys.argv[2]
    password_md5 = sys.argv[3]
    token = login(username, password_md5)
    print(f"✓ 登录成功，获取 token")
    
    # 运行测试
    with open(sys.argv[1]) as f:
        tests = json.load(f)
    
    results = [run_test(t, f"test-{i}", token) for i, t in enumerate(tests)]
    
    with open('test-results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 测试完成，结果保存到 test-results.json")

