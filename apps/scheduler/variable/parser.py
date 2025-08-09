import re
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import json
from datetime import datetime, UTC

from .pool_manager import get_pool_manager
from .type import VariableScope

logger = logging.getLogger(__name__)


class VariableParser:
    """变量解析器 - 支持新架构的变量解析器（系统变量和对话变量都在对话池中）"""
    
    # 变量引用的正则表达式：{{scope.variable_name.nested_path}}
    VARIABLE_PATTERN = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}')
    
    def __init__(self, 
                 user_id: Optional[str] = None,
                 flow_id: Optional[str] = None,
                 conversation_id: Optional[str] = None,
                 user_sub: Optional[str] = None,
                 current_step_id: Optional[str] = None):
        """初始化变量解析器
        
        Args:
            user_id: 用户ID (向后兼容)
            flow_id: 流程ID
            conversation_id: 对话ID
            user_sub: 用户订阅ID (优先使用，用于未来鉴权等需求)
            current_step_id: 当前步骤ID，用于支持{{self.xxx}}语法
        """
        # 优先使用 user_sub，如果没有则使用 user_id
        self.user_id = user_sub if user_sub is not None else user_id
        self.flow_id = flow_id
        self.conversation_id = conversation_id
        self.current_step_id = current_step_id
        self._pool_manager = None
    
    async def _get_pool_manager(self):
        """获取变量池管理器实例"""
        if self._pool_manager is None:
            self._pool_manager = await get_pool_manager()
        return self._pool_manager
    
    async def parse_template(self, template: str) -> str:
        """解析模板字符串，替换其中的变量引用
        
        Args:
            template: 包含变量引用的模板字符串
            
        Returns:
            str: 替换后的字符串
        """
        if not template:
            return template
        
        # 查找所有变量引用
        matches = self.VARIABLE_PATTERN.findall(template)
        
        # 替换每个变量引用
        result = template
        for match in matches:
            try:
                # 解析变量引用
                value = await self._resolve_variable_reference(match)
                
                # 转换为字符串
                str_value = self._convert_to_string(value)
                
                # 替换模板中的变量引用
                result = result.replace(f"{{{{{match}}}}}", str_value)
                
                logger.debug(f"已替换变量: {{{{{match}}}}} -> {str_value}")
                
            except Exception as e:
                logger.warning(f"解析变量引用失败: {{{{{match}}}}} - {e}")
                # 保持原始引用不变
                continue
        
        return result
    
    async def _resolve_variable_reference(self, reference: str) -> Tuple[Any, Any]:
        """解析变量引用
        
        Args:
            reference: 变量引用字符串（不含花括号）
            
        Returns:
            Tuple[Any, Any]: 变量值, 变量类型
        """
        pool_manager = await self._get_pool_manager()
        
        # 解析作用域和变量名
        parts = reference.strip().split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"无效的变量引用格式: {reference}")
        
        scope_str, var_path = parts
        
        # 处理特殊的self作用域
        if scope_str == "self":
            if not self.current_step_id:
                raise ValueError("使用{{self.xxx}}语法时，当前步骤ID不可用")
            # 将self.xxx转换为conversation.current_step_id.xxx
            scope_str = "conversation"
            var_path = f"{self.current_step_id}.{var_path}"
        
        # 确定作用域
        scope_map = {
            "sys": VariableScope.SYSTEM,
            "system": VariableScope.SYSTEM,
            "user": VariableScope.USER,
            "env": VariableScope.ENVIRONMENT,
            "environment": VariableScope.ENVIRONMENT,
            "conversation": VariableScope.CONVERSATION,
            "conv": VariableScope.CONVERSATION,
        }
        
        scope = scope_map.get(scope_str)
        if not scope:
            raise ValueError(f"无效的变量作用域: {scope_str}")
        
        # 解析变量路径
        # 对于conversation作用域，支持节点输出变量格式：conversation.node_id.key
        if scope == VariableScope.CONVERSATION and "." in var_path:
            # 检查是否为节点输出变量（格式：node_id.key）
            # 先尝试获取完整路径作为变量名
            try:
                variable = await pool_manager.get_variable_from_any_pool(
                    name=var_path,  # 使用完整路径作为变量名
                    scope=scope,
                    user_id=self.user_id if scope == VariableScope.USER else None,
                    flow_id=self.flow_id if scope in [VariableScope.SYSTEM, VariableScope.ENVIRONMENT, VariableScope.CONVERSATION] else None,
                    conversation_id=self.conversation_id if scope in [VariableScope.SYSTEM, VariableScope.CONVERSATION] else None
                )
                if variable:
                    return variable.value, variable.var_type
            except:
                pass  # 如果找不到，继续使用原有逻辑
        
        # 原有逻辑：支持嵌套访问如 user.config.api_key
        path_parts = var_path.split(".")
        var_name = path_parts[0]
        
        # 根据作用域获取变量
        variable = await pool_manager.get_variable_from_any_pool(
            name=var_name,
            scope=scope,
            user_id=self.user_id,
            flow_id=self.flow_id,
            conversation_id=self.conversation_id
        )
        
        if not variable:
            raise ValueError(f"变量不存在: {scope_str}.{var_name}")
        
        # 获取变量值
        value = variable.value
        var_type = variable.var_type
        
        # 如果有嵌套路径，继续解析
        for path_part in path_parts[1:]:
            if isinstance(value, dict):
                value = value.get(path_part)
            elif isinstance(value, list) and path_part.isdigit():
                try:
                    value = value[int(path_part)]
                except IndexError:
                    value = None
            else:
                raise ValueError(f"无法访问路径: {var_path}")
        
        return value, var_type
    
    async def extract_variables(self, template: str) -> List[str]:
        """提取模板中的所有变量引用
        
        Args:
            template: 模板字符串
            
        Returns:
            List[str]: 变量引用列表
        """
        if not template:
            return []
        
        matches = self.VARIABLE_PATTERN.findall(template)
        return [f"{{{{{match}}}}}" for match in matches]
    
    async def validate_template(self, template: str) -> Tuple[bool, List[str]]:
        """验证模板中的变量引用是否都存在
        
        Args:
            template: 模板字符串
            
        Returns:
            Tuple[bool, List[str]]: (是否全部有效, 无效的变量引用列表)
        """
        if not template:
            return True, []
        
        matches = self.VARIABLE_PATTERN.findall(template)
        invalid_refs = []
        
        for match in matches:
            try:
                await self._resolve_variable_reference(match)
            except Exception:
                invalid_refs.append(f"{{{{{match}}}}}")
        
        return len(invalid_refs) == 0, invalid_refs
    
    async def parse_json_template(self, json_template: Union[str, Dict, List]) -> Union[str, Dict, List]:
        """解析JSON格式的模板，递归处理所有字符串值中的变量引用
        
        Args:
            json_template: JSON模板（字符串、字典或列表）
            
        Returns:
            Union[str, Dict, List]: 解析后的JSON
        """
        if isinstance(json_template, str):
            return await self.parse_template(json_template)
        elif isinstance(json_template, dict):
            result = {}
            for key, value in json_template.items():
                # 键也可能包含变量引用
                parsed_key = await self.parse_template(str(key))
                parsed_value = await self.parse_json_template(value)
                result[parsed_key] = parsed_value
            return result
        elif isinstance(json_template, list):
            result = []
            for item in json_template:
                parsed_item = await self.parse_json_template(item)
                result.append(parsed_item)
            return result
        else:
            # 其他类型直接返回
            return json_template
    
    async def update_system_variables(self, context: Dict[str, Any]):
        """更新系统变量的值
        
        Args:
            context: 系统上下文信息
        """
        if not self.conversation_id:
            logger.warning("无法更新系统变量：缺少conversation_id")
            return
        
        # 确保对话变量池存在
        await self.create_conversation_pool_if_needed()
        
        pool_manager = await self._get_pool_manager()
        
        # 预定义的系统变量映射
        system_var_mappings = {
            "query": context.get("question", ""),
            "files": context.get("files", []),
            "dialogue_count": context.get("dialogue_count", 0),
            "app_id": context.get("app_id", ""),
            "flow_id": context.get("flow_id", self.flow_id or ""),
            "user_id": context.get("user_sub", self.user_id or ""),
            "session_id": context.get("session_id", ""),
            "conversation_id": self.conversation_id,
            "timestamp": datetime.now(UTC).timestamp(),
        }
        
        # 获取对话变量池
        conversation_pool = await pool_manager.get_conversation_pool(self.conversation_id)
        if not conversation_pool:
            logger.error(f"对话变量池不存在，无法更新系统变量: {self.conversation_id}")
            return
        
        # 更新系统变量
        updated_count = 0
        for var_name, var_value in system_var_mappings.items():
            try:
                success = await conversation_pool.update_system_variable(var_name, var_value)
                if success:
                    updated_count += 1
                    logger.debug(f"已更新系统变量: {var_name} = {var_value}")
                else:
                    logger.warning(f"系统变量更新失败: {var_name}")
            except Exception as e:
                logger.warning(f"更新系统变量失败: {var_name} - {e}")
        
        logger.info(f"系统变量更新完成: {updated_count}/{len(system_var_mappings)} 个变量更新成功")
    
    async def update_conversation_variable(self, var_name: str, value: Any) -> bool:
        """更新对话变量的值
        
        Args:
            var_name: 变量名
            value: 新值
            
        Returns:
            bool: 是否更新成功
        """
        if not self.conversation_id:
            logger.warning("无法更新对话变量：缺少conversation_id")
            return False
        
        pool_manager = await self._get_pool_manager()
        conversation_pool = await pool_manager.get_conversation_pool(self.conversation_id)
        
        if not conversation_pool:
            logger.warning(f"无法获取对话变量池: {self.conversation_id}")
            return False
        
        try:
            await conversation_pool.update_variable(var_name, value=value)
            logger.info(f"已更新对话变量: {var_name} = {value}")
            return True
        except Exception as e:
            logger.error(f"更新对话变量失败: {var_name} - {e}")
            return False
    
    async def create_conversation_pool_if_needed(self) -> bool:
        """如果需要，创建对话变量池
        
        Returns:
            bool: 是否创建成功
        """
        if not self.conversation_id or not self.flow_id:
            return False
        
        pool_manager = await self._get_pool_manager()
        existing_pool = await pool_manager.get_conversation_pool(self.conversation_id)
        
        if existing_pool:
            return True
        
        try:
            await pool_manager.create_conversation_pool(self.conversation_id, self.flow_id)
            logger.info(f"已创建对话变量池: {self.conversation_id}")
            return True
        except Exception as e:
            logger.error(f"创建对话变量池失败: {self.conversation_id} - {e}")
            return False
    
    def _convert_to_string(self, value: Any) -> str:
        """将值转换为字符串
        
        Args:
            value: 要转换的值
            
        Returns:
            str: 字符串表示
        """
        if value is None:
            return ""
        elif isinstance(value, str):
            return value
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            except (TypeError, ValueError):
                return str(value)
        else:
            return str(value)
    
    @classmethod
    def escape_variable_reference(cls, text: str) -> str:
        """转义变量引用，防止被解析
        
        Args:
            text: 包含变量引用的文本
            
        Returns:
            str: 转义后的文本
        """
        return text.replace("{{", "\\{\\{").replace("}}", "\\}\\}")
    
    @classmethod
    def unescape_variable_reference(cls, text: str) -> str:
        """取消转义变量引用
        
        Args:
            text: 转义的文本
            
        Returns:
            str: 取消转义后的文本
        """
        return text.replace("\\{\\{", "{{").replace("\\}\\}", "}}")


class VariableReferenceBuilder:
    """变量引用构建器 - 帮助构建标准的变量引用字符串"""
    
    @staticmethod
    def system(var_name: str, nested_path: Optional[str] = None) -> str:
        """构建系统变量引用
        
        Args:
            var_name: 变量名
            nested_path: 嵌套路径（如 config.api_key）
            
        Returns:
            str: 变量引用字符串
        """
        if nested_path:
            return f"{{{{sys.{var_name}.{nested_path}}}}}"
        return f"{{{{sys.{var_name}}}}}"
    
    @staticmethod
    def user(var_name: str, nested_path: Optional[str] = None) -> str:
        """构建用户变量引用
        
        Args:
            var_name: 变量名
            nested_path: 嵌套路径
            
        Returns:
            str: 变量引用字符串
        """
        if nested_path:
            return f"{{{{user.{var_name}.{nested_path}}}}}"
        return f"{{{{user.{var_name}}}}}"
    
    @staticmethod
    def environment(var_name: str, nested_path: Optional[str] = None) -> str:
        """构建环境变量引用
        
        Args:
            var_name: 变量名
            nested_path: 嵌套路径
            
        Returns:
            str: 变量引用字符串
        """
        if nested_path:
            return f"{{{{env.{var_name}.{nested_path}}}}}"
        return f"{{{{env.{var_name}}}}}"
    
    @staticmethod
    def conversation(var_name: str, nested_path: Optional[str] = None) -> str:
        """构建对话变量引用
        
        Args:
            var_name: 变量名
            nested_path: 嵌套路径
            
        Returns:
            str: 变量引用字符串
        """
        if nested_path:
            return f"{{{{conversation.{var_name}.{nested_path}}}}}"
        return f"{{{{conversation.{var_name}}}}}"


class VariableContext:
    """变量上下文管理器 - 管理局部变量作用域"""
    
    def __init__(self, 
                 parser: VariableParser,
                 parent_context: Optional["VariableContext"] = None):
        """初始化变量上下文
        
        Args:
            parser: 变量解析器
            parent_context: 父级上下文（用于嵌套作用域）
        """
        self.parser = parser
        self.parent_context = parent_context
        self._local_variables: Dict[str, Any] = {}
    
    def set_local_variable(self, name: str, value: Any):
        """设置局部变量
        
        Args:
            name: 变量名
            value: 变量值
        """
        self._local_variables[name] = value
    
    def get_local_variable(self, name: str) -> Any:
        """获取局部变量
        
        Args:
            name: 变量名
            
        Returns:
            Any: 变量值
        """
        if name in self._local_variables:
            return self._local_variables[name]
        elif self.parent_context:
            return self.parent_context.get_local_variable(name)
        return None
    
    async def parse_with_locals(self, template: str) -> str:
        """使用局部变量解析模板
        
        Args:
            template: 模板字符串
            
        Returns:
            str: 解析后的字符串
        """
        # 首先用局部变量替换
        result = template
        
        # 替换局部变量（使用简单的 ${var_name} 语法）
        for var_name, var_value in self._local_variables.items():
            pattern = f"${{{var_name}}}"
            str_value = self.parser._convert_to_string(var_value)
            result = result.replace(pattern, str_value)
        
        # 然后用全局变量解析器处理剩余的变量引用
        return await self.parser.parse_template(result)
    
    def create_child_context(self) -> "VariableContext":
        """创建子级上下文
        
        Returns:
            VariableContext: 子级上下文
        """
        return VariableContext(self.parser, self) 