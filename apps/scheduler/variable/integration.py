"""变量解析与工作流调度器集成"""

import logging
from typing import Any, Dict, List, Optional, Union

from apps.scheduler.variable.parser import VariableParser
from apps.scheduler.variable.pool import get_variable_pool
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
            
            pool = await get_variable_pool()
            # 在内部将conversation_id作为flow_id传递
            await pool.add_variable(
                name=name,
                var_type=var_type,
                scope=VariableScope.CONVERSATION,
                value=value,
                flow_id=conversation_id  # 统一使用flow_id
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
            pool = await get_variable_pool()
            # 在内部将conversation_id作为flow_id传递
            await pool.update_variable(
                name=name,
                scope=VariableScope.CONVERSATION,
                value=value,
                flow_id=conversation_id  # 统一使用flow_id
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
            pool = await get_variable_pool()
            await pool.clear_conversation_variables(conversation_id)
            logger.info(f"已清理对话 {conversation_id} 的变量")
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


# 为现有调度器提供的扩展方法
class CoreCallExtension:
    """CoreCall的变量支持扩展"""
    
    @staticmethod
    async def enhanced_set_input(core_call_instance, executor) -> None:
        """增强版的_set_input方法，支持变量解析
        
        Args:
            core_call_instance: CoreCall实例
            executor: StepExecutor实例
        """
        # 调用原始的_set_input方法
        original_set_input = getattr(core_call_instance.__class__, '_original_set_input', None)
        if original_set_input:
            await original_set_input(core_call_instance, executor)
        else:
            # 如果没有原始方法，执行基本的输入设置
            from apps.scheduler.call.core import CoreCall
            core_call_instance._sys_vars = CoreCall._assemble_call_vars(executor)
            input_data = await core_call_instance._init(core_call_instance._sys_vars)
            core_call_instance.input = input_data.model_dump(by_alias=True, exclude_none=True)
        
        # 解析输入中的变量引用
        if hasattr(core_call_instance, 'input') and core_call_instance.input:
            # 首先初始化系统变量
            context = {
                "question": executor.question,
                "user_sub": executor.task.ids.user_sub,
                "flow_id": executor.task.state.flow_id if executor.task.state else None,
                "session_id": executor.task.ids.session_id,
                "app_id": executor.task.state.app_id if executor.task.state else None,
                "conversation_id": executor.task.ids.session_id,  # 使用session_id作为conversation_id
            }
            
            await VariableIntegration.initialize_system_variables(context)
            
            # 解析输入变量
            core_call_instance.input = await VariableIntegration.parse_call_input(
                core_call_instance.input,
                user_sub=executor.task.ids.user_sub,
                flow_id=executor.task.state.flow_id if executor.task.state else None,
                conversation_id=executor.task.ids.session_id
            )


class LLMCallExtension:
    """LLM Call的变量支持扩展"""
    
    @staticmethod
    async def enhanced_prepare_message(llm_instance, call_vars) -> list[dict[str, Any]]:
        """增强版的_prepare_message方法，支持变量解析
        
        Args:
            llm_instance: LLM实例
            call_vars: CallVars实例
            
        Returns:
            list[dict[str, Any]]: 解析后的消息列表
        """
        # 调用原始的_prepare_message方法
        original_prepare_message = getattr(llm_instance.__class__, '_original_prepare_message', None)
        if original_prepare_message:
            messages = await original_prepare_message(llm_instance, call_vars)
        else:
            # 如果没有原始方法，返回基本消息
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": call_vars.question}
            ]
        
        # 解析消息中的变量引用
        parsed_messages = []
        for message in messages:
            if "content" in message and isinstance(message["content"], str):
                parsed_content = await VariableIntegration.parse_template_string(
                    message["content"],
                    user_sub=call_vars.ids.user_sub,
                    flow_id=call_vars.ids.flow_id,
                    conversation_id=call_vars.ids.session_id
                )
                parsed_messages.append({
                    **message,
                    "content": parsed_content
                })
            else:
                parsed_messages.append(message)
        
        return parsed_messages


def monkey_patch_scheduler():
    """为现有调度器添加变量支持的猴子补丁"""
    try:
        # 为CoreCall添加变量支持
        from apps.scheduler.call.core import CoreCall
        
        # 保存原始方法
        original_set_input = getattr(CoreCall, '_set_input', None)
        if original_set_input:
            setattr(CoreCall, '_original_set_input', original_set_input)
        
        # 替换为增强版本
        setattr(CoreCall, '_set_input', CoreCallExtension.enhanced_set_input)
        # 为LLM Call添加变量支持
        try:
            from apps.scheduler.call.llm.llm import LLM
            
            # 保存原始方法
            original_prepare_message = getattr(LLM, '_prepare_message', None)
            if original_prepare_message:
                setattr(LLM, '_original_prepare_message', original_prepare_message)
            
            # 替换为增强版本
            setattr(LLM, '_prepare_message', LLMCallExtension.enhanced_prepare_message)
        
        except ImportError:
            logger.warning("LLM Call 不存在，跳过LLM变量支持")
        
        logger.info("变量解析功能已集成到调度器中")
        
    except Exception as e:
        logger.error(f"集成变量解析功能失败: {e}")
        raise


# 在模块导入时自动应用补丁
try:
    monkey_patch_scheduler()
except Exception as e:
    logger.error(f"自动应用变量解析补丁失败: {e}")