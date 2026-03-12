import requests
import json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFzdHJib3QiLCJleHAiOjE3NzM5Mjg2NzR9.ydidjdZgPDOU52-40Sdks6yIDrLcN2SeNjgcL_j8ozo"

tests = json.load(open('test-cases.json'))
results = []

for i, test in enumerate(tests):
    print(f"\n测试 {i+1}/{len(tests)}: {test['name']}")
    
    response = requests.post(
        "http://127.0.0.1:6185/api/chat/send",
        headers={'Authorization': f'Bearer {TOKEN}'},
        json={'message': f"使用 execute_shell 执行：{test['command']}", 'session_id': f'test-{i}'},
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
                    if data.get('type') == 'complete':
                        output = data.get('data', '')
                        break
                except:
                    pass
    
    passed = test['expected'] in output
    results.append({'name': test['name'], 'passed': passed, 'output': output[:500]})
    print(f"  {'✓' if passed else '✗'} {test['name']}")

json.dump(results, open('test-results-manual.json', 'w'), indent=2, ensure_ascii=False)
print(f"\n结果保存到 test-results-manual.json")
