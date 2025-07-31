"""变量解析与工作流调度器集成"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from apps.scheduler.variable.parser import VariableParser
from apps.scheduler.variable.pool_manager import get_pool_manager
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
                              conversation_id: Optional[str] = None) -> Union[str, Dict, List]:
        """解析Call输入中的变量引用
        
        Args:
            input_data: 输入数据
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            
        Returns:
            Dict[str, Any]: 解析后的输入数据
        """
        try:
            parser = VariableParser(
                user_sub=user_sub,
                flow_id=flow_id,
                conversation_id=conversation_id
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
        conversation_id: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """解析单个变量引用
        
        Args:
            reference: 变量引用字符串（如 "{{user.name}}" 或 "user.name"）
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            
        Returns:
            Tuple[Any, Any]: 解析后的变量值和变量类型
        """
        try:
            parser = VariableParser(
                user_id=user_sub,
                flow_id=flow_id,
                conversation_id=conversation_id
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
    
    @staticmethod
    async def add_conversation_variable(name: str,
                                      value: Any,
                                      conversation_id: str,
                                      var_type_str: str = "string") -> bool:
        """添加对话级变量
        
        Args:
            name: 变量名
            value: 变量值
            conversation_id: 对话ID（在内部作为flow_id使用）
            var_type_str: 变量类型字符串
            
        Returns:
            bool: 是否添加成功
        """
        try:
            from apps.scheduler.variable.type import VariableType
            
            # 转换变量类型
            var_type = VariableType(var_type_str)
            
            pool_manager = await get_pool_manager()
            # 获取对话变量池（如果不存在会抛出异常）
            conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
            if not conversation_pool:
                logger.error(f"对话变量池不存在: {conversation_id}")
                return False
            
            await conversation_pool.add_variable(
                name=name,
                var_type=var_type,
                value=value,
                description=f"对话变量: {name}"
            )
            
            logger.debug(f"已添加对话变量: {name} = {value}")
            return True
        except Exception as e:
            logger.error(f"添加对话变量失败: {e}")
            return False
    
    @staticmethod
    async def update_conversation_variable(name: str,
                                         value: Any,
                                         conversation_id: str) -> bool:
        """更新对话级变量
        
        Args:
            name: 变量名
            value: 新值
            conversation_id: 对话ID
            
        Returns:
            bool: 是否更新成功
        """
        try:
            pool_manager = await get_pool_manager()
            # 获取对话变量池
            conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
            if not conversation_pool:
                logger.error(f"对话变量池不存在: {conversation_id}")
                return False
            
            await conversation_pool.update_variable(
                name=name,
                value=value
            )
            
            logger.debug(f"已更新对话变量: {name} = {value}")
            return True
        except Exception as e:
            logger.error(f"更新对话变量失败: {e}")
            return False
    
    @staticmethod
    async def extract_output_variables(output_data: Dict[str, Any],
                                     conversation_id: str,
                                     step_name: str) -> None:
        """从步骤输出中提取变量并设置为对话级变量
        
        Args:
            output_data: 步骤输出数据
            conversation_id: 对话ID
            step_name: 步骤名称
        """
        try:
            # 将整个输出作为对象变量存储
            await VariableIntegration.add_conversation_variable(
                name=f"step_{step_name}_output",
                value=output_data,
                conversation_id=conversation_id,
                var_type_str="object"
            )
            
            # 如果输出中有特定的变量定义，也可以单独提取
            if isinstance(output_data, dict):
                for key, value in output_data.items():
                    if key.startswith("var_"):
                        # 以 var_ 开头的字段被视为变量定义
                        var_name = key[4:]  # 移除 var_ 前缀
                        await VariableIntegration.add_conversation_variable(
                            name=var_name,
                            value=value,
                            conversation_id=conversation_id,
                            var_type_str="string"
                        )
            
        except Exception as e:
            logger.error(f"提取输出变量失败: {e}")
    
    @staticmethod
    async def clear_conversation_context(conversation_id: str) -> None:
        """清理对话上下文中的变量
        
        Args:
            conversation_id: 对话ID
        """
        try:
            pool_manager = await get_pool_manager()
            # 移除对话变量池
            success = await pool_manager.remove_conversation_pool(conversation_id)
            if success:
                logger.info(f"已清理对话 {conversation_id} 的变量")
            else:
                logger.warning(f"对话变量池不存在: {conversation_id}")
        except Exception as e:
            logger.error(f"清理对话变量失败: {e}")
    
    @staticmethod
    async def validate_variable_references(template: str,
                                         user_sub: str,
                                         flow_id: Optional[str] = None,
                                         conversation_id: Optional[str] = None) -> tuple[bool, list[str]]:
        """验证模板中的变量引用是否有效
        
        Args:
            template: 模板字符串
            user_sub: 用户ID
            flow_id: 流程ID
            conversation_id: 对话ID
            
        Returns:
            tuple[bool, list[str]]: (是否全部有效, 无效的变量引用列表)
        """
        try:
            parser = VariableParser(
                user_sub=user_sub,
                flow_id=flow_id,
                conversation_id=conversation_id
            )
            
            return await parser.validate_template(template)
        except Exception as e:
            logger.error(f"验证变量引用失败: {e}")
            return False, [str(e)]


# 注意：原本的 monkey_patch_scheduler 和相关扩展类已被移除
# 因为 CoreCall 类现在已经内置了完整的变量解析功能
# 这些代码是旧版本的遗留，会导致循环导入问题