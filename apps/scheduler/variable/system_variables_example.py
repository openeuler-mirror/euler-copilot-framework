"""
系统变量使用示例

演示系统变量的正确初始化、更新和访问流程
"""

import asyncio
from datetime import datetime, UTC
from typing import Dict, Any

from .pool_manager import get_pool_manager
from .parser import VariableParser, VariableReferenceBuilder
from .type import VariableScope


async def demonstrate_system_variables():
    """演示系统变量的完整工作流程"""
    
    # 模拟对话参数
    user_id = "user123"
    flow_id = "flow456" 
    conversation_id = "conv789"
    
    print("=== 系统变量演示 ===\n")
    
    # 1. 创建变量解析器（会自动创建对话池并初始化系统变量）
    print("1. 创建变量解析器并初始化对话变量池...")
    parser = VariableParser(
        user_id=user_id,
        flow_id=flow_id,
        conversation_id=conversation_id
    )
    
    # 确保对话池存在
    success = await parser.create_conversation_pool_if_needed()
    print(f"   对话池创建结果: {'成功' if success else '失败'}")
    
    # 2. 检查系统变量是否已正确初始化
    print("\n2. 检查初始化的系统变量...")
    pool_manager = await get_pool_manager()
    conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
    
    if conversation_pool:
        system_vars = await conversation_pool.list_system_variables()
        print(f"   已初始化 {len(system_vars)} 个系统变量:")
        for var in system_vars:
            print(f"   - {var.name}: {var.value} ({var.var_type.value})")
    
    # 3. 更新系统变量（模拟对话开始）
    print("\n3. 更新系统变量...")
    context = {
        "question": "请帮我分析这个数据文件",
        "files": [{"name": "data.csv", "size": 1024, "type": "text/csv"}],
        "dialogue_count": 1,
        "app_id": "app001",
        "user_sub": user_id,
        "session_id": "session123"
    }
    
    await parser.update_system_variables(context)
    print("   系统变量更新完成")
    
    # 4. 验证系统变量已正确更新
    print("\n4. 验证系统变量更新结果...")
    updated_vars = await conversation_pool.list_system_variables()
    for var in updated_vars:
        if var.name in ["query", "files", "dialogue_count", "app_id", "user_id", "session_id"]:
            print(f"   - {var.name}: {var.value}")
    
    # 5. 使用变量引用解析模板
    print("\n5. 解析包含系统变量的模板...")
    template = """
用户查询: {{sys.query}}
对话轮数: {{sys.dialogue_count}}
流程ID: {{sys.flow_id}}
用户ID: {{sys.user_id}}
文件数量: {{sys.files.length}}
"""
    
    try:
        parsed_result = await parser.parse_template(template)
        print("   模板解析结果:")
        print(parsed_result)
    except Exception as e:
        print(f"   模板解析失败: {e}")
    
    # 6. 验证系统变量的只读性
    print("\n6. 验证系统变量的只读保护...")
    try:
        # 尝试直接修改系统变量（应该失败）
        await conversation_pool.update_variable("query", value="恶意修改")
        print("   ❌ 错误：系统变量被意外修改")
    except PermissionError:
        print("   ✅ 正确：系统变量只读保护生效")
    except Exception as e:
        print(f"   🤔 意外错误: {e}")
    
    # 7. 展示系统变量的强制更新（内部使用）
    print("\n7. 演示系统变量的内部更新...")
    success = await conversation_pool.update_system_variable("dialogue_count", 2)
    if success:
        updated_var = await conversation_pool.get_variable("dialogue_count")
        print(f"   ✅ 系统变量内部更新成功: dialogue_count = {updated_var.value}")
    else:
        print("   ❌ 系统变量内部更新失败")
    
    # 8. 清理
    print("\n8. 清理对话变量池...")
    removed = await pool_manager.remove_conversation_pool(conversation_id)
    print(f"   清理结果: {'成功' if removed else '失败'}")
    
    print("\n=== 演示完成 ===")


async def demonstrate_variable_references():
    """演示系统变量引用的构建和使用"""
    
    print("\n=== 变量引用演示 ===\n")
    
    # 构建各种变量引用
    print("1. 变量引用构建示例:")
    
    # 系统变量引用
    query_ref = VariableReferenceBuilder.system("query")
    files_ref = VariableReferenceBuilder.system("files", "0.name")  # 嵌套访问
    
    # 用户变量引用
    api_key_ref = VariableReferenceBuilder.user("api_key")
    
    # 环境变量引用
    db_url_ref = VariableReferenceBuilder.environment("database_url")
    
    # 对话变量引用
    history_ref = VariableReferenceBuilder.conversation("chat_history")
    
    print(f"   系统变量 - 用户查询: {query_ref}")
    print(f"   系统变量 - 首个文件名: {files_ref}")
    print(f"   用户变量 - API密钥: {api_key_ref}")
    print(f"   环境变量 - 数据库: {db_url_ref}")
    print(f"   对话变量 - 聊天历史: {history_ref}")
    
    # 构建复杂模板
    print("\n2. 复杂模板示例:")
    complex_template = f"""
# 对话上下文
- 用户: {query_ref}
- 轮次: {VariableReferenceBuilder.system("dialogue_count")}
- 时间: {VariableReferenceBuilder.system("timestamp")}

# 文件信息
- 文件列表: {VariableReferenceBuilder.system("files")}
- 文件数量: {VariableReferenceBuilder.system("files", "length")}

# 会话信息
- 对话ID: {VariableReferenceBuilder.system("conversation_id")}
- 流程ID: {VariableReferenceBuilder.system("flow_id")}
- 用户ID: {VariableReferenceBuilder.system("user_id")}
"""
    
    print(complex_template)
    
    print("=== 引用演示完成 ===")


async def validate_system_variable_persistence():
    """验证系统变量的持久化"""
    
    print("\n=== 持久化验证 ===\n")
    
    conversation_id = "test_persistence_conv"
    flow_id = "test_persistence_flow"
    
    # 创建对话池
    pool_manager = await get_pool_manager()
    conversation_pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
    
    print("1. 检查新创建池的系统变量...")
    system_vars_before = await conversation_pool.list_system_variables()
    print(f"   创建后的系统变量数量: {len(system_vars_before)}")
    
    # 模拟应用重启 - 重新获取池
    print("\n2. 模拟重新加载...")
    await pool_manager.remove_conversation_pool(conversation_id)
    
    # 重新创建同一个对话池
    conversation_pool_reloaded = await pool_manager.create_conversation_pool(conversation_id, flow_id)
    system_vars_after = await conversation_pool_reloaded.list_system_variables()
    
    print(f"   重新加载后的系统变量数量: {len(system_vars_after)}")
    
    # 验证变量是否一致
    vars_before_names = {var.name for var in system_vars_before}
    vars_after_names = {var.name for var in system_vars_after}
    
    if vars_before_names == vars_after_names:
        print("   ✅ 系统变量持久化验证成功")
    else:
        print("   ❌ 系统变量持久化验证失败")
        print(f"      之前: {vars_before_names}")
        print(f"      之后: {vars_after_names}")
    
    # 清理
    await pool_manager.remove_conversation_pool(conversation_id)
    
    print("=== 持久化验证完成 ===")


if __name__ == "__main__":
    async def main():
        """运行所有演示"""
        try:
            await demonstrate_system_variables()
            await demonstrate_variable_references()
            await validate_system_variable_persistence()
        except Exception as e:
            print(f"演示过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(main()) 