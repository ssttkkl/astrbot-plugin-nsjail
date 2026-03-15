"""测试状态保持问题"""
import asyncio
import sys
sys.path.insert(0, '.')

from astrbot_plugin_nsjail.sandbox_manager import SandboxManager, SandboxConfig

async def test_state_persistence():
    config = SandboxConfig(
        plugin_data_dir="/tmp/test_nsjail",
        skills_dir="/tmp/test_skills",
        enable_network=False
    )
    manager = SandboxManager(config)
    
    session_id = "test_state"
    
    try:
        # 第一步：设置环境变量和切换目录
        result1 = await manager.execute_in_sandbox(
            session_id=session_id,
            command="export MY_VAR=hello && mkdir -p subdir && cd subdir && pwd"
        )
        print("=== 第一步 ===")
        print(f"stdout: {result1['stdout']}")
        print(f"stderr: {result1['stderr']}")
        
        # 第二步：尝试读取环境变量和检查目录
        result2 = await manager.execute_in_sandbox(
            session_id=session_id,
            command="echo MY_VAR=$MY_VAR && pwd"
        )
        print("\n=== 第二步 ===")
        print(f"stdout: {result2['stdout']}")
        print(f"stderr: {result2['stderr']}")
        
        # 分析结果
        print("\n=== 分析 ===")
        if "MY_VAR=" in result2['stdout'] and "hello" not in result2['stdout']:
            print("❌ 环境变量丢失（预期问题）")
        else:
            print("✅ 环境变量保持")
            
        if "/workspace/subdir" in result1['stdout'] and "/workspace/subdir" not in result2['stdout']:
            print("❌ 工作目录丢失（预期问题）")
        else:
            print("✅ 工作目录保持")
            
    finally:
        await manager.destroy_sandbox(session_id)
        await manager.terminate()

if __name__ == "__main__":
    asyncio.run(test_state_persistence())
