"""变量系统与外部组件的集成接口"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from apps.scheduler.variable.pool_manager import get_pool_manager
from apps.scheduler.variable.parser import VariableParser
from apps.scheduler.variable.type import VariableScope

logger = logging.getLogger(__name__)


class VariableIntegration:
    """变量解析集成类 - 为现有调度器提供变量功能"""
    
    @staticmethod
    async def initialize_system_variables(context: Dict[str, Any]) -> None:
        """初始化系统变量
        
        Args:
            context: 系统上下文信息，包括用户查询、文件等
        """
        try:
            parser = VariableParser(
                user_sub=context.get("user_sub"),
                flow_id=context.get("flow_id"),
                conversation_id=context.get("conversation_id")
            )
            
            # 更新系统变量
            await parser.update_system_variables(context)
            
            logger.info("系统变量已初始化")
        except Exception as e:
            logger.error(f"初始化系统变量失败: {e}")
            raise
    
    @staticmethod
    async def parse_call_input(input_data: Dict[str, Any], 
                              user_sub: str,
                              flow_id: Optional[str] = None,
                              conversation_id: Optional[str] = None,
                              current_step_id: Optional[str] = None) -> Union[str, Dict, List]:
        """解析Call输入中的变量引用
        
        Args:
            input_data: 输入数据
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            current_step_id: 当前步骤ID，用于支持{{self.xxx}}语法
            
        Returns:
            Dict[str, Any]: 解析后的输入数据
        """
        try:
            parser = VariableParser(
                user_sub=user_sub,
                flow_id=flow_id,
                conversation_id=conversation_id,
                current_step_id=current_step_id
            )
            
            # 递归解析JSON模板中的变量引用
            parsed_input = await parser.parse_json_template(input_data)
            
            return parsed_input
        
        except Exception as e:
            logger.warning(f"解析Call输入变量失败: {e}")
            # 如果解析失败，返回原始输入
            return input_data

    @staticmethod
    async def resolve_variable_reference(
        reference: str,
        user_sub: str,
        flow_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        current_step_id: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """解析单个变量引用
        
        Args:
            reference: 变量引用字符串（如 "{{user.name}}" 或 "user.name"）
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            current_step_id: 当前步骤ID，用于支持{{self.xxx}}语法
            
        Returns:
            Tuple[Any, Any]: 解析后的变量值和变量类型
        """
        try:
            parser = VariableParser(
                user_id=user_sub,
                flow_id=flow_id,
                conversation_id=conversation_id,
                current_step_id=current_step_id
            )
            
            # 清理引用字符串（移除花括号）
            clean_reference = reference.strip("{}")
            
            # 使用解析器解析变量引用
            resolved_value, resolved_type = await parser._resolve_variable_reference(clean_reference)
            
            return resolved_value, resolved_type
        
        except Exception as e:
            logger.error(f"解析变量引用失败: {reference}, 错误: {e}")
            raise
    
    @staticmethod
    async def save_conversation_variable(
        var_name: str,
        value: Any,
        var_type: str = "string",
        description: str = "",
        user_sub: str = "",
        flow_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> bool:
        """保存对话变量
        
        Args:
            var_name: 变量名（不包含scope前缀）
            value: 变量值
            var_type: 变量类型
            description: 变量描述
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if not conversation_id:
                logger.warning("无法保存对话变量：缺少conversation_id")
                return False
            
            # 直接使用pool_manager，避免解析器的复杂逻辑
            pool_manager = await get_pool_manager()
            conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
            
            if not conversation_pool:
                logger.warning(f"无法获取对话变量池: {conversation_id}")
                return False
            
            # 转换变量类型
            from apps.scheduler.variable.type import VariableType
            try:
                var_type_enum = VariableType(var_type)
            except ValueError:
                var_type_enum = VariableType.STRING
                logger.warning(f"未知的变量类型 {var_type}，使用默认类型 string")
            
            # 尝试更新变量，如果不存在则创建
            try:
                await conversation_pool.update_variable(var_name, value=value)
                logger.debug(f"对话变量已更新: {var_name} = {value}")
                return True
            except ValueError as e:
                if "不存在" in str(e):
                    # 变量不存在，创建新变量
                    await conversation_pool.add_variable(
                        name=var_name,
                        var_type=var_type_enum,
                        value=value,
                        description=description,
                        created_by=user_sub or "system"
                    )
                    logger.debug(f"对话变量已创建: {var_name} = {value}")
                    return True
                else:
                    raise  # 其他错误重新抛出
                    
        except Exception as e:
            logger.error(f"保存对话变量失败: {var_name} - {e}")
            return False
    
    @staticmethod
    async def parse_template_string(template: str,
                                   user_sub: str,
                                   flow_id: Optional[str] = None,
                                   conversation_id: Optional[str] = None) -> str:
        """解析模板字符串中的变量引用
        
        Args:
            template: 模板字符串
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            
        Returns:
            str: 解析后的字符串
        """
        try:
            parser = VariableParser(
                user_sub=user_sub,
                flow_id=flow_id,
                conversation_id=conversation_id
            )
            
            return await parser.parse_template(template)
        except Exception as e:
            logger.warning(f"解析模板字符串失败: {e}")
            # 如果解析失败，返回原始模板
            return template


# 注意：原本的 monkey_patch_scheduler 和相关扩展类已被移除
# 因为 CoreCall 类现在已经内置了完整的变量解析功能
# 这些代码是旧版本的遗留，会导致循环导入问题