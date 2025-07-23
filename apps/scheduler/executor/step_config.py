# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""步骤执行器配置"""

from typing import Set

# 可以直接写入 conversation.key 格式的节点类型配置
# 这些节点类型的输出变量不会添加 step_id 前缀
# 
# 说明：
# - 添加新的节点类型时，直接在这个集合中添加对应的 call_id 或节点名称即可
# - 支持大小写敏感匹配，建议同时添加大小写版本以确保兼容性
# - 这些节点的输出变量将保存为 conversation.key 格式
# - 其他节点的输出变量将保存为 conversation.step_id.key 格式
DIRECT_CONVERSATION_VARIABLE_NODE_TYPES: Set[str] = {
    # 开始节点相关
    "Start",
    "start", 
    
    # 输入节点相关  
    "Input",
    "UserInput",
    "input",
    
    # 未来可能的节点类型示例（取消注释即可启用）
    # "GlobalConfig",     # 全局配置节点
    # "SessionInit",      # 会话初始化节点
    # "SystemConfig",     # 系统配置节点
}

# 可以通过节点名称模式匹配的规则
# 如果节点名称或step_id（转换为小写后）以这些字符串开头，则使用直接格式
# 
# 说明：
# - 这些模式用于匹配节点名称或step_id的前缀（不区分大小写）
# - 比如："start"会匹配 "StartProcess"、"start_workflow" 等
# - 适用于无法提前知道具体节点名称，但可以通过命名规范识别的场景
DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS: Set[str] = {
    "start",       # 匹配所有以start开头的节点
    "init",        # 匹配所有以init开头的节点
    "input",       # 匹配所有以input开头的节点
    
    # 可以根据需要添加更多模式
    # "config",    # 匹配配置相关节点
    # "setup",     # 匹配设置相关节点
}

def should_use_direct_conversation_format(call_id: str, step_name: str, step_id: str) -> bool:
    """
    判断是否应该使用直接的 conversation.key 格式
    
    Args:
        call_id: 节点的call_id
        step_name: 节点名称
        step_id: 节点ID
        
    Returns:
        bool: True表示使用 conversation.key，False表示使用 conversation.step_id.key
    """
    # 1. 检查call_id是否在直接写入列表中
    if call_id in DIRECT_CONVERSATION_VARIABLE_NODE_TYPES:
        return True
    
    # 2. 检查节点名称是否在直接写入列表中
    if step_name in DIRECT_CONVERSATION_VARIABLE_NODE_TYPES:
        return True
    
    # 3. 检查节点名称是否匹配模式
    step_name_lower = step_name.lower()
    for pattern in DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS:
        if step_name_lower.startswith(pattern):
            return True
    
    # 4. 检查step_id是否匹配模式
    step_id_lower = step_id.lower()
    for pattern in DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS:
        if step_id_lower.startswith(pattern):
            return True
    
    return False 