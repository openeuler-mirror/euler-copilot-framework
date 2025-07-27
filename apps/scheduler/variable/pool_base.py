import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, UTC

from apps.common.mongo import MongoDB
from .base import BaseVariable, VariableMetadata
from .type import VariableType, VariableScope
from .variables import create_variable, VARIABLE_CLASS_MAP

logger = logging.getLogger(__name__)


class BaseVariablePool(ABC):
    """变量池基类"""
    
    def __init__(self, pool_id: str, scope: VariableScope):
        """初始化变量池
        
        Args:
            pool_id: 池标识符（如user_id、flow_id、conversation_id等）
            scope: 池作用域
        """
        self.pool_id = pool_id
        self.scope = scope
        self._variables: Dict[str, BaseVariable] = {}
        self._initialized = False
        self._lock = asyncio.Lock()
        
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    async def initialize(self):
        """初始化变量池"""
        async with self._lock:
            if not self._initialized:
                await self._load_variables()
                await self._setup_default_variables()
                self._initialized = True
                logger.info(f"已初始化变量池: {self.__class__.__name__}({self.pool_id})")
    
    @abstractmethod
    async def _load_variables(self):
        """从存储加载变量"""
        pass
    
    @abstractmethod
    async def _setup_default_variables(self):
        """设置默认变量"""
        pass
    
    @abstractmethod
    def can_modify(self) -> bool:
        """检查是否允许修改变量"""
        pass
    
    async def add_variable(self, 
                          name: str, 
                          var_type: VariableType, 
                          value: Any = None,
                          description: Optional[str] = None,
                          created_by: Optional[str] = None,
                          is_system: bool = False) -> BaseVariable:
        """添加变量"""
        if not self.can_modify():
            raise PermissionError(f"不允许修改{self.scope.value}级变量")
        
        if name in self._variables:
            raise ValueError(f"变量 {name} 已存在")
        
        # 创建变量元数据
        metadata = VariableMetadata(
            name=name,
            var_type=var_type,
            scope=self.scope,
            description=description,
            user_sub=getattr(self, 'user_id', None),
            flow_id=getattr(self, 'flow_id', None),
            conversation_id=getattr(self, 'conversation_id', None),
            created_by=created_by or "system",
            is_system=is_system  # 标记是否为系统变量
        )
        
        # 创建变量
        variable = create_variable(metadata, value)
        self._variables[name] = variable
        
        # 持久化
        await self._persist_variable(variable)
        
        logger.info(f"已添加{'系统' if is_system else ''}变量: {name} 到池 {self.pool_id}")
        return variable
    
    async def update_variable(self, 
                             name: str, 
                             value: Optional[Any] = None,
                             var_type: Optional[VariableType] = None,
                             description: Optional[str] = None,
                             force_system_update: bool = False) -> BaseVariable:
        """更新变量"""
        if name not in self._variables:
            raise ValueError(f"变量 {name} 不存在")
        
        variable = self._variables[name]
        
        # 检查系统变量的修改权限
        if hasattr(variable.metadata, 'is_system') and variable.metadata.is_system and not force_system_update:
            raise PermissionError(f"系统变量 {name} 不允许修改")
        
        if not self.can_modify() and not force_system_update:
            raise PermissionError(f"不允许修改{self.scope.value}级变量")
        
        # 更新字段
        if value is not None:
            variable.value = value
        if var_type is not None:
            variable.metadata.var_type = var_type
        if description is not None:
            variable.metadata.description = description
            
        variable.metadata.updated_at = datetime.now(UTC)
        
        # 持久化
        await self._persist_variable(variable)
        
        logger.info(f"已更新变量: {name} 在池 {self.pool_id}, 值为{value}")
        return variable
    
    async def delete_variable(self, name: str) -> bool:
        """删除变量"""
        if not self.can_modify():
            raise PermissionError(f"不允许修改{self.scope.value}级变量")
        
        if name not in self._variables:
            return False
        
        variable = self._variables[name]
        
        # 检查是否为系统变量
        if hasattr(variable.metadata, 'is_system') and variable.metadata.is_system:
            raise PermissionError(f"系统变量 {name} 不允许删除")
        
        del self._variables[name]
        
        # 从数据库删除
        await self._delete_variable_from_db(variable)
        
        logger.info(f"已删除变量: {name} 从池 {self.pool_id}")
        return True
    
    async def get_variable(self, name: str) -> Optional[BaseVariable]:
        """获取变量"""
        return self._variables.get(name)
    
    async def list_variables(self, include_system: bool = True) -> List[BaseVariable]:
        """列出所有变量"""
        if include_system:
            return list(self._variables.values())
        else:
            # 只返回非系统变量
            return [var for var in self._variables.values() 
                   if not (hasattr(var.metadata, 'is_system') and var.metadata.is_system)]
    
    async def list_system_variables(self) -> List[BaseVariable]:
        """列出系统变量"""
        return [var for var in self._variables.values() 
               if hasattr(var.metadata, 'is_system') and var.metadata.is_system]
    
    async def has_variable(self, name: str) -> bool:
        """检查变量是否存在"""
        return name in self._variables
    
    async def copy_variables(self) -> Dict[str, BaseVariable]:
        """拷贝所有变量"""
        copied = {}
        for name, variable in self._variables.items():
            # 创建新的元数据
            new_metadata = VariableMetadata(
                name=variable.metadata.name,
                var_type=variable.metadata.var_type,
                scope=variable.metadata.scope,
                description=variable.metadata.description,
                user_sub=variable.metadata.user_sub,
                flow_id=variable.metadata.flow_id,
                conversation_id=variable.metadata.conversation_id,
                created_by=variable.metadata.created_by,
                is_system=getattr(variable.metadata, 'is_system', False)
            )
            # 创建新的变量实例
            copied[name] = create_variable(new_metadata, variable.value)
        return copied
    
    async def _persist_variable(self, variable: BaseVariable):
        """持久化变量"""
        try:
            collection = MongoDB().get_collection("variables")
            data = variable.serialize()
            
            # 构建查询条件
            query = {
                "metadata.name": variable.name,
                "metadata.scope": variable.scope.value
            }
            
            # 添加池特定的查询条件
            self._add_pool_query_conditions(query, variable)
            
            # 更新或插入
            from pymongo import WriteConcern
            result = await collection.with_options(
                write_concern=WriteConcern(w="majority", j=True)
            ).replace_one(query, data, upsert=True)
            
            if not (result.acknowledged and (result.matched_count > 0 or result.upserted_id)):
                raise RuntimeError(f"变量持久化失败: {variable.name}")
                
        except Exception as e:
            logger.error(f"持久化变量失败: {e}")
            raise
    
    async def _delete_variable_from_db(self, variable: BaseVariable):
        """从数据库删除变量"""
        try:
            collection = MongoDB().get_collection("variables")
            
            query = {
                "metadata.name": variable.name,
                "metadata.scope": variable.scope.value
            }
            
            # 添加池特定的查询条件
            self._add_pool_query_conditions(query, variable)
            
            from pymongo import WriteConcern
            result = await collection.with_options(
                write_concern=WriteConcern(w="majority", j=True)
            ).delete_one(query)
            
            if not result.acknowledged:
                raise RuntimeError(f"变量删除失败: {variable.name}")
                
        except Exception as e:
            logger.error(f"删除变量失败: {e}")
            raise
    
    @abstractmethod
    def _add_pool_query_conditions(self, query: Dict[str, Any], variable: BaseVariable):
        """添加池特定的查询条件"""
        pass


class UserVariablePool(BaseVariablePool):
    """用户变量池"""
    
    def __init__(self, user_id: str):
        super().__init__(user_id, VariableScope.USER)
        self.user_id = user_id
    
    async def _load_variables(self):
        """从数据库加载用户变量"""
        try:
            collection = MongoDB().get_collection("variables")
            cursor = collection.find({
                "metadata.scope": VariableScope.USER.value,
                "metadata.user_sub": self.user_id
            })
            
            loaded_count = 0
            async for doc in cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._variables[variable.name] = variable
                                loaded_count += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"用户变量 {var_name} 数据损坏: {e}")
            
            logger.debug(f"用户 {self.user_id} 加载变量完成: {loaded_count} 个")
            
        except Exception as e:
            logger.error(f"加载用户变量失败: {e}")
    
    async def _setup_default_variables(self):
        """用户变量池不需要默认变量"""
        pass
    
    def can_modify(self) -> bool:
        """用户变量允许修改"""
        return True
    
    def _add_pool_query_conditions(self, query: Dict[str, Any], variable: BaseVariable):
        """添加用户变量池的查询条件"""
        query["metadata.user_sub"] = self.user_id


class FlowVariablePool(BaseVariablePool):
    """流程变量池（环境变量 + 系统变量模板 + 对话变量模板）"""
    
    def __init__(self, flow_id: str, parent_flow_id: Optional[str] = None):
        super().__init__(flow_id, VariableScope.ENVIRONMENT)  # 保持主要scope为ENVIRONMENT
        self.flow_id = flow_id
        self.parent_flow_id = parent_flow_id
        
        # 分别存储不同类型的变量
        # _variables 继续存储环境变量（保持向后兼容）
        self._system_templates: Dict[str, BaseVariable] = {}  # 系统变量模板
        self._conversation_templates: Dict[str, BaseVariable] = {}  # 对话变量模板
    
    async def _load_variables(self):
        """从数据库加载所有类型的变量（环境变量 + 模板变量）"""
        try:
            collection = MongoDB().get_collection("variables")
            loaded_counts = {"environment": 0, "system_templates": 0, "conversation_templates": 0}
            
            # 1. 加载环境变量
            env_cursor = collection.find({
                "metadata.scope": VariableScope.ENVIRONMENT.value,
                "metadata.flow_id": self.flow_id
            })
            
            async for doc in env_cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._variables[variable.name] = variable
                                loaded_counts["environment"] += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"环境变量 {var_name} 数据损坏: {e}")
            
            # 2. 加载系统变量模板
            system_template_cursor = collection.find({
                "metadata.scope": VariableScope.SYSTEM.value,
                "metadata.flow_id": self.flow_id,
                "metadata.is_template": True
            })
            
            async for doc in system_template_cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._system_templates[variable.name] = variable
                                loaded_counts["system_templates"] += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"系统变量模板 {var_name} 数据损坏: {e}")
            
            # 3. 加载对话变量模板
            conv_template_cursor = collection.find({
                "metadata.scope": VariableScope.CONVERSATION.value,
                "metadata.flow_id": self.flow_id,
                "metadata.is_template": True
            })
            
            async for doc in conv_template_cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._conversation_templates[variable.name] = variable
                                loaded_counts["conversation_templates"] += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"对话变量模板 {var_name} 数据损坏: {e}")
            
            total_loaded = sum(loaded_counts.values())
            logger.debug(f"流程 {self.flow_id} 加载变量完成: 环境变量{loaded_counts['environment']}个, "
                        f"系统模板{loaded_counts['system_templates']}个, "
                        f"对话模板{loaded_counts['conversation_templates']}个, 总计{total_loaded}个")
            
        except Exception as e:
            logger.error(f"加载流程变量失败: {e}")
    
    async def _setup_default_variables(self):
        """设置默认的系统变量模板"""
        from datetime import datetime, UTC
        
        # 定义系统变量模板（这些是模板，不是实例）
        system_var_templates = [
            ("query", VariableType.STRING, "用户查询内容", ""),
            ("files", VariableType.ARRAY_FILE, "用户上传的文件列表", []),
            ("dialogue_count", VariableType.NUMBER, "对话轮数", 0),
            ("app_id", VariableType.STRING, "应用ID", ""),
            ("flow_id", VariableType.STRING, "工作流ID", self.flow_id),
            ("user_id", VariableType.STRING, "用户ID", ""),
            ("session_id", VariableType.STRING, "会话ID", ""),
            ("conversation_id", VariableType.STRING, "对话ID", ""),
            ("timestamp", VariableType.NUMBER, "当前时间戳", 0),
        ]
        
        created_count = 0
        for var_name, var_type, description, default_value in system_var_templates:
            # 如果系统变量模板不存在，才创建
            if var_name not in self._system_templates:
                metadata = VariableMetadata(
                    name=var_name,
                    var_type=var_type,
                    scope=VariableScope.SYSTEM,
                    description=description,
                    flow_id=self.flow_id,
                    created_by="system",
                    is_system=True,
                    is_template=True  # 标记为模板
                )
                variable = create_variable(metadata, default_value)
                self._system_templates[var_name] = variable
                
                # 持久化模板到数据库
                try:
                    await self._persist_variable(variable)
                    created_count += 1
                    logger.debug(f"已持久化系统变量模板: {var_name}")
                except Exception as e:
                    logger.error(f"持久化系统变量模板失败: {var_name} - {e}")
        
        if created_count > 0:
            logger.info(f"已为流程 {self.flow_id} 初始化 {created_count} 个系统变量模板")
    
    def can_modify(self) -> bool:
        """环境变量允许修改"""
        return True
    
    # === 系统变量模板相关方法 ===
    
    async def get_system_template(self, name: str) -> Optional[BaseVariable]:
        """获取系统变量模板"""
        return self._system_templates.get(name)
    
    async def list_system_templates(self) -> List[BaseVariable]:
        """列出所有系统变量模板"""
        return list(self._system_templates.values())
    
    async def add_system_template(self, name: str, var_type: VariableType, 
                                  default_value: Any = None, description: str = None) -> BaseVariable:
        """添加系统变量模板"""
        if name in self._system_templates:
            raise ValueError(f"系统变量模板 {name} 已存在")
        
        metadata = VariableMetadata(
            name=name,
            var_type=var_type,
            scope=VariableScope.SYSTEM,
            description=description,
            flow_id=self.flow_id,
            created_by="system",
            is_system=True,
            is_template=True
        )
        
        variable = create_variable(metadata, default_value)
        self._system_templates[name] = variable
        
        # 持久化到数据库
        await self._persist_variable(variable)
        
        logger.info(f"已添加系统变量模板: {name} 到流程 {self.flow_id}")
        return variable
    
    # === 对话变量模板相关方法 ===
    
    async def get_conversation_template(self, name: str) -> Optional[BaseVariable]:
        """获取对话变量模板"""
        return self._conversation_templates.get(name)
    
    async def list_conversation_templates(self) -> List[BaseVariable]:
        """列出所有对话变量模板"""
        return list(self._conversation_templates.values())
    
    async def add_conversation_template(self, name: str, var_type: VariableType,
                                       default_value: Any = None, description: str = None,
                                       created_by: str = None) -> BaseVariable:
        """添加对话变量模板"""
        if name in self._conversation_templates:
            raise ValueError(f"对话变量模板 {name} 已存在")
        
        metadata = VariableMetadata(
            name=name,
            var_type=var_type,
            scope=VariableScope.CONVERSATION,
            description=description,
            flow_id=self.flow_id,
            created_by=created_by or "user",
            is_system=False,
            is_template=True
        )
        
        variable = create_variable(metadata, default_value)
        self._conversation_templates[name] = variable
        
        # 持久化到数据库
        await self._persist_variable(variable)
        
        logger.info(f"已添加对话变量模板: {name} 到流程 {self.flow_id}")
        return variable
    
    # === 重写基类方法支持多scope查询 ===
    
    async def get_variable_by_scope(self, name: str, scope: VariableScope) -> Optional[BaseVariable]:
        """根据作用域获取变量"""
        if scope == VariableScope.ENVIRONMENT:
            return self._variables.get(name)
        elif scope == VariableScope.SYSTEM:
            return self._system_templates.get(name)
        elif scope == VariableScope.CONVERSATION:
            return self._conversation_templates.get(name)
        else:
            return None
    
    async def list_variables_by_scope(self, scope: VariableScope) -> List[BaseVariable]:
        """根据作用域列出变量"""
        if scope == VariableScope.ENVIRONMENT:
            return list(self._variables.values())
        elif scope == VariableScope.SYSTEM:
            return list(self._system_templates.values())
        elif scope == VariableScope.CONVERSATION:
            return list(self._conversation_templates.values())
        else:
            return []
    
    # === 重写基类方法支持多字典操作 ===
    
    async def update_variable(self, name: str, value: Any = None, 
                             var_type: Optional[VariableType] = None, 
                             description: Optional[str] = None,
                             force_system_update: bool = False) -> BaseVariable:
        """更新变量（支持多字典查找）"""
        
        # 先在环境变量中查找
        if name in self._variables:
            return await super().update_variable(name, value, var_type, description, force_system_update)
        
        # 在系统变量模板中查找
        elif name in self._system_templates:
            variable = self._system_templates[name]
            
            # 检查权限
            if not force_system_update and getattr(variable.metadata, 'is_system', False):
                raise PermissionError(f"系统变量 {name} 不允许直接修改")
            
            # 更新变量
            if value is not None:
                variable.value = value
            if var_type is not None:
                variable.metadata.var_type = var_type
            if description is not None:
                variable.metadata.description = description
            
            # 持久化
            await self._persist_variable(variable)
            return variable
        
        # 在对话变量模板中查找
        elif name in self._conversation_templates:
            variable = self._conversation_templates[name]
            
            # 更新变量
            if value is not None:
                variable.value = value
            if var_type is not None:
                variable.metadata.var_type = var_type
            if description is not None:
                variable.metadata.description = description
            
            # 持久化
            await self._persist_variable(variable)
            return variable
        
        else:
            raise ValueError(f"变量 {name} 不存在")
    
    async def delete_variable(self, name: str) -> bool:
        """删除变量（支持多字典查找）"""
        
        # 先在环境变量中查找
        if name in self._variables:
            return await super().delete_variable(name)
        
        # 在系统变量模板中查找
        elif name in self._system_templates:
            variable = self._system_templates[name]
            
            # 检查权限
            if getattr(variable.metadata, 'is_system', False):
                raise PermissionError(f"系统变量模板 {name} 不允许删除")
            
            del self._system_templates[name]
            await self._delete_variable_from_db(variable)
            return True
        
        # 在对话变量模板中查找
        elif name in self._conversation_templates:
            variable = self._conversation_templates[name]
            del self._conversation_templates[name]
            await self._delete_variable_from_db(variable)
            return True
        
        else:
            return False
    
    async def get_variable(self, name: str) -> Optional[BaseVariable]:
        """获取变量（支持多字典查找）"""
        
        # 先在环境变量中查找
        if name in self._variables:
            return self._variables[name]
        
        # 在系统变量模板中查找
        elif name in self._system_templates:
            return self._system_templates[name]
        
        # 在对话变量模板中查找
        elif name in self._conversation_templates:
            return self._conversation_templates[name]
        
        else:
            return None
    
    def _add_pool_query_conditions(self, query: Dict[str, Any], variable: BaseVariable):
        """添加环境变量池的查询条件"""
        query["metadata.flow_id"] = self.flow_id
    
    async def inherit_from_parent(self, parent_pool: "FlowVariablePool"):
        """从父流程继承环境变量"""
        parent_variables = await parent_pool.copy_variables()
        for name, variable in parent_variables.items():
            # 更新元数据中的flow_id
            variable.metadata.flow_id = self.flow_id
            self._variables[name] = variable
            # 持久化继承的变量
            await self._persist_variable(variable)
        
        logger.info(f"流程 {self.flow_id} 从父流程 {parent_pool.flow_id} 继承了 {len(parent_variables)} 个环境变量")


class ConversationVariablePool(BaseVariablePool):
    """对话变量池 - 包含系统变量和对话变量"""
    
    def __init__(self, conversation_id: str, flow_id: str):
        super().__init__(conversation_id, VariableScope.CONVERSATION)
        self.conversation_id = conversation_id
        self.flow_id = flow_id
    
    async def _load_variables(self):
        """从数据库加载对话变量"""
        try:
            collection = MongoDB().get_collection("variables")
            cursor = collection.find({
                "metadata.scope": VariableScope.CONVERSATION.value,
                "metadata.conversation_id": self.conversation_id
            })
            
            loaded_count = 0
            async for doc in cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._variables[variable.name] = variable
                                loaded_count += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"对话变量 {var_name} 数据损坏: {e}")
            
            logger.debug(f"对话 {self.conversation_id} 加载变量完成: {loaded_count} 个")
            
        except Exception as e:
            logger.error(f"加载对话变量失败: {e}")
    
    async def _setup_default_variables(self):
        """从flow模板继承系统变量和对话变量"""
        from .pool_manager import get_pool_manager
        
        try:
            pool_manager = await get_pool_manager()
            flow_pool = await pool_manager.get_flow_pool(self.flow_id)
            
            if not flow_pool:
                logger.warning(f"未找到流程池 {self.flow_id}，无法继承变量模板")
                return
            
            created_count = 0
            
            # 1. 从系统变量模板创建系统变量实例
            system_templates = await flow_pool.list_system_templates()
            for template in system_templates:
                if template.name not in self._variables:
                    # 创建系统变量实例（不是模板）
                    metadata = VariableMetadata(
                        name=template.name,
                        var_type=template.var_type,
                        scope=VariableScope.CONVERSATION,  # 存储在对话作用域
                        description=template.metadata.description,
                        flow_id=self.flow_id,
                        conversation_id=self.conversation_id,
                        created_by="system",
                        is_system=True,  # 标记为系统变量
                        is_template=False  # 这是实例，不是模板
                    )
                    
                    # 使用模板的默认值创建实例
                    variable = create_variable(metadata, template.value)
                    self._variables[template.name] = variable
                    
                    # 持久化系统变量实例
                    try:
                        await self._persist_variable(variable)
                        created_count += 1
                        logger.debug(f"已从模板创建系统变量实例: {template.name}")
                    except Exception as e:
                        logger.error(f"持久化系统变量实例失败: {template.name} - {e}")
            
            # 2. 从对话变量模板创建对话变量实例
            conversation_templates = await flow_pool.list_conversation_templates()
            for template in conversation_templates:
                if template.name not in self._variables:
                    # 创建对话变量实例
                    metadata = VariableMetadata(
                        name=template.name,
                        var_type=template.var_type,
                        scope=VariableScope.CONVERSATION,
                        description=template.metadata.description,
                        flow_id=self.flow_id,
                        conversation_id=self.conversation_id,
                        created_by=template.metadata.created_by,
                        is_system=False,  # 对话变量
                        is_template=False  # 这是实例，不是模板
                    )
                    
                    # 使用模板的默认值创建实例
                    variable = create_variable(metadata, template.value)
                    self._variables[template.name] = variable
                    
                    # 持久化对话变量实例
                    try:
                        await self._persist_variable(variable)
                        created_count += 1
                        logger.debug(f"已从模板创建对话变量实例: {template.name}")
                    except Exception as e:
                        logger.error(f"持久化对话变量实例失败: {template.name} - {e}")
            
            if created_count > 0:
                logger.info(f"已为对话 {self.conversation_id} 从流程模板继承 {created_count} 个变量")
                
        except Exception as e:
            logger.error(f"从流程模板继承变量失败: {e}")
    
    def can_modify(self) -> bool:
        """对话变量允许修改"""
        return True
    
    def _add_pool_query_conditions(self, query: Dict[str, Any], variable: BaseVariable):
        """添加对话变量池的查询条件"""
        query["metadata.conversation_id"] = self.conversation_id
        query["metadata.flow_id"] = self.flow_id
    
    async def update_system_variable(self, name: str, value: Any) -> bool:
        """更新系统变量的值（系统内部调用）"""
        try:
            await self.update_variable(name, value=value, force_system_update=True)
            return True
        except Exception as e:
            logger.error(f"更新系统变量失败: {name} - {e}")
            return False
    
    async def inherit_from_conversation_template(self, template_pool: Optional["ConversationVariablePool"] = None):
        """从对话模板池继承变量（如果存在）"""
        if template_pool:
            template_variables = await template_pool.copy_variables()
            for name, variable in template_variables.items():
                # 只继承非系统变量
                if not (hasattr(variable.metadata, 'is_system') and variable.metadata.is_system):
                    variable.metadata.conversation_id = self.conversation_id
                    self._variables[name] = variable
            
            logger.info(f"对话 {self.conversation_id} 从模板继承了 {len(template_variables)} 个变量") 