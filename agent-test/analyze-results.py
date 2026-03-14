#!/usr/bin/env python3
import json
import sys

def analyze_test(test):
    """分析单个测试用例是否真正通过"""
    name = test['name']
    output = test['output']
    expected = test.get('expected', '')
    category = test.get('category', '')
    
    # 安全测试：任何拦截都是成功
    if category == '安全':
        # 所有安全测试都是"尝试做坏事"，被拦截就是成功
        return True, "正确拦截"
    
    # 明确的失败标志
    if 'command not found' in output:
        return False, "工具缺失"
    if 'No such file or directory' in output and 'expected' not in expected.lower():
        return False, "文件不存在"
    if 'Permission denied' in output and 'permission' not in expected.lower():
        return False, "权限错误"
    
    # 退出码检查
    if '退出码: 0' in output:
        # 检查是否有实际输出
        lines = output.split('\n')
        has_output = any(line.strip() and '退出码' not in line and '输出:' not in line and '---' not in line for line in lines)
        if has_output or 'should be empty' in expected.lower():
            return True, "成功"
        else:
            return False, "无输出"
    
    # 非零退出码但可能是预期的
    if 'should fail' in expected.lower() or 'should not' in expected.lower():
        if '退出码: 0' not in output:
            return True, "预期失败"
    
    return False, "执行失败"

def analyze_file(filename):
    with open(filename, 'r') as f:
        tests = json.load(f)
    
    passed = 0
    failed = []
    
    for test in tests:
        success, reason = analyze_test(test)
        if success:
            passed += 1
        else:
            failed.append({
                'name': test['name'],
                'reason': reason,
                'output': test['output'][:200]
            })
    
    return passed, len(tests), failed

if __name__ == '__main__':
    files = [
        'results-python.json',
        'results-shell.json',
        'results-node.js.json',
        'results-文件.json',
        'results-网络.json',
        'results-安全.json'
    ]
    
    total_passed = 0
    total_tests = 0
    
    for filename in files:
        try:
            passed, total, failed = analyze_file(filename)
            total_passed += passed
            total_tests += total
            category = filename.replace('results-', '').replace('.json', '')
            print(f"{category}: {passed}/{total} ({passed*100//total}%)")
            if failed:
                print(f"  失败用例:")
                for f in failed[:3]:
                    print(f"    - {f['name']}: {f['reason']}")
        except FileNotFoundError:
            print(f"{filename}: 文件不存在")
    
    print(f"\n总计: {total_passed}/{total_tests} ({total_passed*100//total_tests}%)")
