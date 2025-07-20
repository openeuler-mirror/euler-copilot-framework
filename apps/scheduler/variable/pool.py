import logging
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, UTC

from apps.common.mongo import MongoDB
from .base import BaseVariable, VariableMetadata
from .type import VariableType, VariableScope
from .variables import create_variable, VARIABLE_CLASS_MAP

logger = logging.getLogger(__name__)


class VariablePool:
    """变量池 - 管理所有作用域的变量"""
    
    def __init__(self):
        """初始化变量池"""
        # 内存缓存：scope -> {variable_name: variable}
        self._variables: Dict[VariableScope, Dict[str, BaseVariable]] = {
            VariableScope.SYSTEM: {},
            VariableScope.USER: {},
            VariableScope.ENVIRONMENT: {},
            VariableScope.CONVERSATION: {},
        }
        
        # 上下文相关的变量缓存
        self._user_variables: Dict[str, Dict[str, BaseVariable]] = defaultdict(dict)  # user_sub -> variables
        self._env_variables: Dict[str, Dict[str, BaseVariable]] = defaultdict(dict)   # flow_id -> variables
        self._conv_variables: Dict[str, Dict[str, BaseVariable]] = defaultdict(dict)  # flow_id -> variables (对话级变量)
        
        # 系统级变量定义
        self._system_variables_initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """初始化变量池，加载系统变量"""
        async with self._lock:
            if not self._system_variables_initialized:
                await self._initialize_system_variables()
                self._system_variables_initialized = True
    
    async def _initialize_system_variables(self):
        """初始化系统级变量"""
        system_vars = [
            ("query", VariableType.STRING, "用户查询内容", ""),
            ("files", VariableType.ARRAY_FILE, "用户上传的文件列表", []),
            ("dialogue_count", VariableType.NUMBER, "对话轮数", 0),
            ("app_id", VariableType.STRING, "应用ID", ""),
            ("flow_id", VariableType.STRING, "工作流ID", ""),
            ("user_id", VariableType.STRING, "用户ID", ""),
            ("session_id", VariableType.STRING, "会话ID", ""),
            ("timestamp", VariableType.NUMBER, "当前时间戳", 0),
        ]
        
        for var_name, var_type, description, default_value in system_vars:
            metadata = VariableMetadata(
                name=var_name,
                var_type=var_type,
                scope=VariableScope.SYSTEM,
                description=description,
                created_by="system"
            )
            variable = create_variable(metadata, default_value)
            self._variables[VariableScope.SYSTEM][var_name] = variable
        
        logger.info(f"已初始化 {len(system_vars)} 个系统级变量")
    
    async def add_variable(self, 
                          name: str, 
                          var_type: VariableType, 
                          scope: VariableScope, 
                          value: Any = None,
                          description: Optional[str] = None,
                          user_sub: Optional[str] = None,
                          flow_id: Optional[str] = None) -> BaseVariable:
        """添加变量
        
        Args:
            name: 变量名
            var_type: 变量类型
            scope: 作用域
            value: 初始值
            description: 描述
            user_sub: 用户ID（用户级变量必需）
            flow_id: 流程ID（环境级变量必需）
            
        Returns:
            BaseVariable: 创建的变量
        """
        await self.initialize()
        
        # 验证作用域相关参数
        if scope == VariableScope.SYSTEM:
            raise ValueError("不能直接添加系统级变量")
        elif scope == VariableScope.USER and not user_sub:
            raise ValueError("用户级变量必须指定 user_sub")
        elif scope == VariableScope.ENVIRONMENT and not flow_id:
            raise ValueError("环境级变量必须指定 flow_id")
        elif scope == VariableScope.CONVERSATION and not flow_id:
            raise ValueError("对话级变量必须指定 flow_id")
        
        # 检查变量是否已存在
        existing_var = await self.get_variable(name, scope, user_sub, flow_id)
        if existing_var:
            raise ValueError(f"变量 {name} 在作用域 {scope.value} 中已存在")
        
        # 创建变量元数据
        metadata = VariableMetadata(
            name=name,
            var_type=var_type,
            scope=scope,
            description=description,
            user_sub=user_sub,
            flow_id=flow_id,
            created_by=user_sub or "system"
        )
        
        # 创建变量
        variable = create_variable(metadata, value)
        
        # 存储到对应的缓存中
        await self._store_variable(variable)
        
        # 持久化存储 - 为了更好的用户体验，对话级变量也进行持久化
        await self._persist_variable(variable)
        
        logger.info(f"已添加变量: {name} ({var_type.value}) 到作用域 {scope.value}")
        return variable
    
    async def update_variable(self, 
                             name: str, 
                             scope: VariableScope,
                             value: Optional[Any] = None,
                             var_type: Optional[VariableType] = None,
                             description: Optional[str] = None,
                             user_sub: Optional[str] = None,
                             flow_id: Optional[str] = None) -> BaseVariable:
        """更新变量值、类型或描述
        
        Args:
            name: 变量名
            scope: 作用域
            value: 新值（可选）
            var_type: 新变量类型（可选）
            description: 新描述（可选）
            user_sub: 用户ID
            flow_id: 流程ID
            
        Returns:
            BaseVariable: 更新后的变量
        """
        variable = await self.get_variable(name, scope, user_sub, flow_id)
        if not variable:
            raise ValueError(f"变量 {name} 在作用域 {scope.value} 中不存在")
        
        # 检查权限
        if user_sub and not variable.can_access(user_sub):
            raise PermissionError(f"用户 {user_sub} 没有权限修改变量 {name}")
        
        # 至少需要更新一个字段
        if value is None and var_type is None and description is None:
            raise ValueError("至少需要指定一个要更新的字段（value、var_type 或 description）")
        
        # 更新字段
        if value is not None:
            variable.value = value
        if var_type is not None:
            variable.metadata.var_type = var_type
        if description is not None:
            variable.metadata.description = description
            
        # 更新时间戳
        variable.metadata.updated_at = datetime.now(UTC)
        
        # 更新缓存
        await self._store_variable(variable)
        
        # 持久化更新 - 为了更好的用户体验，对话级变量也进行持久化
        await self._persist_variable(variable)
        
        logger.info(f"已更新变量: {name} 在作用域 {scope.value}")
        return variable
    
    async def delete_variable(self, 
                             name: str, 
                             scope: VariableScope,
                             user_sub: Optional[str] = None,
                             flow_id: Optional[str] = None) -> bool:
        """删除变量
        
        Args:
            name: 变量名
            scope: 作用域
            user_sub: 用户ID
            flow_id: 流程ID
            
        Returns:
            bool: 是否删除成功
        """
        if scope == VariableScope.SYSTEM:
            raise ValueError("不能删除系统级变量")
        
        variable = await self.get_variable(name, scope, user_sub, flow_id)
        if not variable:
            return False
        
        # 检查权限
        if user_sub and not variable.can_access(user_sub):
            raise PermissionError(f"用户 {user_sub} 没有权限删除变量 {name}")
        
        # 从缓存中删除
        await self._remove_variable_from_cache(variable)
        # 从数据库删除
        await self._delete_variable_from_db(variable)
        
        logger.info(f"已删除变量: {name} 从作用域 {scope.value}")
        return True
    
    async def get_variable(self, 
                          name: str, 
                          scope: VariableScope,
                          user_sub: Optional[str] = None,
                          flow_id: Optional[str] = None) -> Optional[BaseVariable]:
        """获取变量
        
        Args:
            name: 变量名
            scope: 作用域
            user_sub: 用户ID
            flow_id: 流程ID
            
        Returns:
            Optional[BaseVariable]: 变量或None
        """
        await self.initialize()
        
        # 根据作用域从对应缓存中查找
        if scope == VariableScope.SYSTEM:
            return self._variables[VariableScope.SYSTEM].get(name)
        elif scope == VariableScope.USER and user_sub:
            # 先从缓存查找
            if name in self._user_variables[user_sub]:
                return self._user_variables[user_sub][name]
            # 从数据库加载
            return await self._load_user_variable(name, user_sub)
        elif scope == VariableScope.ENVIRONMENT and flow_id:
            # 先从缓存查找
            if name in self._env_variables[flow_id]:
                return self._env_variables[flow_id][name]
            # 从数据库加载
            return await self._load_env_variable(name, flow_id)
        elif scope == VariableScope.CONVERSATION and flow_id:
            # 先从缓存查找
            if name in self._conv_variables[flow_id]:
                return self._conv_variables[flow_id][name]
            # 从数据库加载
            return await self._load_conv_variable(name, flow_id)
        
        return None
    
    async def list_variables(self, 
                            scope: VariableScope,
                            user_sub: Optional[str] = None,
                            flow_id: Optional[str] = None) -> List[BaseVariable]:
        """列出指定作用域的所有变量
        
        Args:
            scope: 作用域
            user_sub: 用户ID
            flow_id: 流程ID
            
        Returns:
            List[BaseVariable]: 变量列表
        """
        await self.initialize()
        
        if scope == VariableScope.SYSTEM:
            return list(self._variables[VariableScope.SYSTEM].values())
        elif scope == VariableScope.USER and user_sub:
            # 加载用户的所有变量
            await self._load_all_user_variables(user_sub)
            return list(self._user_variables[user_sub].values())
        elif scope == VariableScope.ENVIRONMENT and flow_id:
            # 加载环境的所有变量
            await self._load_all_env_variables(flow_id)
            return list(self._env_variables[flow_id].values())
        elif scope == VariableScope.CONVERSATION and flow_id:
            # 加载对话级的所有变量
            await self._load_all_conv_variables(flow_id)
            return list(self._conv_variables[flow_id].values())
        
        return []
    
    async def clear_conversation_variables(self, flow_id: str):
        """清空工作流的对话级变量"""
        if flow_id in self._conv_variables:
            del self._conv_variables[flow_id]
            logger.info(f"已清空工作流 {flow_id} 的对话级变量")
    
    async def refresh_conversation_cache(self, flow_id: str):
        """刷新对话级变量缓存"""
        if flow_id in self._conv_variables:
            # 清空当前缓存
            del self._conv_variables[flow_id]
        
        # 重新加载
        await self._load_all_conv_variables(flow_id)
        logger.info(f"已刷新工作流 {flow_id} 的对话级变量缓存")
    
    async def resolve_variable_reference(self, 
                                       reference: str,
                                       user_sub: Optional[str] = None,
                                       flow_id: Optional[str] = None) -> Any:
        """解析变量引用，如 {{sys.query}} 或 {{user.token}}
        
        Args:
            reference: 变量引用字符串
            user_sub: 用户ID
            flow_id: 流程ID
            
        Returns:
            Any: 变量值
        """
        # 移除 {{ 和 }}
        clean_ref = reference.strip("{}").strip()
        
        # 解析作用域和变量名
        parts = clean_ref.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"无效的变量引用格式: {reference}")
        
        scope_str, var_path = parts
        
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
        
        # 解析变量路径（支持嵌套访问如 user.config.api_key）
        path_parts = var_path.split(".")
        var_name = path_parts[0]
        
        # 获取变量
        variable = await self.get_variable(var_name, scope, user_sub, flow_id)
        if not variable:
            raise ValueError(f"变量不存在: {clean_ref}")
        
        # 获取变量值
        value = variable.value
        
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
        
        return value
    
    async def _store_variable(self, variable: BaseVariable):
        """存储变量到缓存"""
        scope = variable.scope
        name = variable.name
        
        if scope == VariableScope.SYSTEM:
            self._variables[scope][name] = variable
        elif scope == VariableScope.USER:
            user_sub = variable.metadata.user_sub
            if user_sub:
                self._user_variables[user_sub][name] = variable
        elif scope == VariableScope.ENVIRONMENT:
            flow_id = variable.metadata.flow_id
            if flow_id:
                self._env_variables[flow_id][name] = variable
        elif scope == VariableScope.CONVERSATION:
            flow_id = variable.metadata.flow_id
            if flow_id:
                self._conv_variables[flow_id][name] = variable
    
    async def _remove_variable_from_cache(self, variable: BaseVariable):
        """从缓存中移除变量"""
        scope = variable.scope
        name = variable.name
        
        if scope == VariableScope.USER:
            user_sub = variable.metadata.user_sub
            if user_sub and name in self._user_variables[user_sub]:
                del self._user_variables[user_sub][name]
        elif scope == VariableScope.ENVIRONMENT:
            flow_id = variable.metadata.flow_id
            if flow_id and name in self._env_variables[flow_id]:
                del self._env_variables[flow_id][name]
        elif scope == VariableScope.CONVERSATION:
            flow_id = variable.metadata.flow_id
            if flow_id and name in self._conv_variables[flow_id]:
                del self._conv_variables[flow_id][name]
    
    async def _persist_variable(self, variable: BaseVariable):
        """持久化变量到数据库"""
        try:
            collection = MongoDB().get_collection("variables")
            data = variable.serialize()
            
            # 构建查询条件
            query = {
                "metadata.name": variable.name,
                "metadata.scope": variable.scope.value
            }
            
            if variable.scope == VariableScope.USER and variable.metadata.user_sub:
                query["metadata.user_sub"] = variable.metadata.user_sub
            elif variable.scope == VariableScope.ENVIRONMENT and variable.metadata.flow_id:
                query["metadata.flow_id"] = variable.metadata.flow_id
            elif variable.scope == VariableScope.CONVERSATION and variable.metadata.flow_id:
                query["metadata.flow_id"] = variable.metadata.flow_id
            
            # 更新或插入 - 强制等待写入确认
            from pymongo import WriteConcern
            result = await collection.with_options(
                write_concern=WriteConcern(w="majority", j=True)
            ).replace_one(query, data, upsert=True)
            
            # 确保写入成功
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
            
            if variable.scope == VariableScope.USER and variable.metadata.user_sub:
                query["metadata.user_sub"] = variable.metadata.user_sub
            elif variable.scope == VariableScope.ENVIRONMENT and variable.metadata.flow_id:
                query["metadata.flow_id"] = variable.metadata.flow_id
            elif variable.scope == VariableScope.CONVERSATION and variable.metadata.flow_id:
                query["metadata.flow_id"] = variable.metadata.flow_id
            
            # 强制等待写入确认的删除操作
            from pymongo import WriteConcern
            result = await collection.with_options(
                write_concern=WriteConcern(w="majority", j=True)
            ).delete_one(query)
            
            # 确保删除成功
            if not result.acknowledged:
                raise RuntimeError(f"变量删除失败: {variable.name}")
            
        except Exception as e:
            logger.error(f"删除变量失败: {e}")
            raise
    
    async def _load_user_variable(self, name: str, user_sub: str) -> Optional[BaseVariable]:
        """从数据库加载用户变量"""
        try:
            collection = MongoDB().get_collection("variables")
            doc = await collection.find_one({
                "metadata.name": name,
                "metadata.scope": VariableScope.USER.value,
                "metadata.user_sub": user_sub
            })
            
            if doc:
                variable_class_name = doc.get("class")
                if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                    # 找到对应的变量类
                    for var_class in VARIABLE_CLASS_MAP.values():
                        if var_class.__name__ == variable_class_name:
                            try:
                                variable = var_class.deserialize(doc)
                                self._user_variables[user_sub][name] = variable
                                return variable
                            except Exception as e:
                                logger.warning(f"用户变量 {name} 数据损坏，将从数据库删除: {e}")
                                await self._delete_corrupted_variable(doc)
                                return None
            
            return None
            
        except Exception as e:
            logger.error(f"加载用户变量失败: {e}")
            return None
    
    async def _load_env_variable(self, name: str, flow_id: str) -> Optional[BaseVariable]:
        """从数据库加载环境变量"""
        try:
            collection = MongoDB().get_collection("variables")
            doc = await collection.find_one({
                "metadata.name": name,
                "metadata.scope": VariableScope.ENVIRONMENT.value,
                "metadata.flow_id": flow_id
            })
            
            if doc:
                variable_class_name = doc.get("class")
                if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                    # 找到对应的变量类
                    for var_class in VARIABLE_CLASS_MAP.values():
                        if var_class.__name__ == variable_class_name:
                            try:
                                variable = var_class.deserialize(doc)
                                self._env_variables[flow_id][name] = variable
                                return variable
                            except Exception as e:
                                logger.warning(f"环境变量 {name} 数据损坏，将从数据库删除: {e}")
                                await self._delete_corrupted_variable(doc)
                                return None
            
            return None
            
        except Exception as e:
            logger.error(f"加载环境变量失败: {e}")
            return None
    
    async def _load_conv_variable(self, name: str, flow_id: str) -> Optional[BaseVariable]:
        """从数据库加载对话级变量"""
        try:
            collection = MongoDB().get_collection("variables")
            doc = await collection.find_one({
                "metadata.name": name,
                "metadata.scope": VariableScope.CONVERSATION.value,
                "metadata.flow_id": flow_id
            })
            
            if doc:
                variable_class_name = doc.get("class")
                if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                    # 找到对应的变量类
                    for var_class in VARIABLE_CLASS_MAP.values():
                        if var_class.__name__ == variable_class_name:
                            try:
                                variable = var_class.deserialize(doc)
                                self._conv_variables[flow_id][name] = variable
                                return variable
                            except Exception as e:
                                logger.warning(f"对话级变量 {name} 数据损坏，将从数据库删除: {e}")
                                await self._delete_corrupted_variable(doc)
                                return None
            
            return None
            
        except Exception as e:
            logger.error(f"加载对话级变量失败: {e}")
            return None
    
    async def _load_all_user_variables(self, user_sub: str):
        """加载用户的所有变量"""
        try:
            collection = MongoDB().get_collection("variables")
            cursor = collection.find({
                "metadata.scope": VariableScope.USER.value,
                "metadata.user_sub": user_sub
            })
            
            corrupted_count = 0
            loaded_count = 0
            
            async for doc in cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        # 找到对应的变量类
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._user_variables[user_sub][variable.name] = variable
                                loaded_count += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"用户变量 {var_name} 数据损坏，将从数据库删除: {e}")
                    await self._delete_corrupted_variable(doc)
                    corrupted_count += 1
            
            if corrupted_count > 0:
                logger.info(f"用户 {user_sub} 加载变量完成: 成功 {loaded_count} 个，清理损坏数据 {corrupted_count} 个")
            else:
                logger.debug(f"用户 {user_sub} 加载变量完成: {loaded_count} 个")
            
        except Exception as e:
            logger.error(f"加载用户所有变量失败: {e}")
    
    async def _load_all_env_variables(self, flow_id: str):
        """加载环境的所有变量"""
        try:
            collection = MongoDB().get_collection("variables")
            cursor = collection.find({
                "metadata.scope": VariableScope.ENVIRONMENT.value,
                "metadata.flow_id": flow_id
            })
            
            corrupted_count = 0
            loaded_count = 0
            
            async for doc in cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        # 找到对应的变量类
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._env_variables[flow_id][variable.name] = variable
                                loaded_count += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"环境变量 {var_name} 数据损坏，将从数据库删除: {e}")
                    await self._delete_corrupted_variable(doc)
                    corrupted_count += 1
            
            if corrupted_count > 0:
                logger.info(f"环境 {flow_id} 加载变量完成: 成功 {loaded_count} 个，清理损坏数据 {corrupted_count} 个")
            else:
                logger.debug(f"环境 {flow_id} 加载变量完成: {loaded_count} 个")
            
        except Exception as e:
            logger.error(f"加载环境所有变量失败: {e}")
    
    async def _load_all_conv_variables(self, flow_id: str):
        """加载对话级的所有变量"""
        try:
            collection = MongoDB().get_collection("variables")
            cursor = collection.find({
                "metadata.scope": VariableScope.CONVERSATION.value,
                "metadata.flow_id": flow_id
            })
            
            corrupted_count = 0
            loaded_count = 0
            
            async for doc in cursor:
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        # 找到对应的变量类
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                self._conv_variables[flow_id][variable.name] = variable
                                loaded_count += 1
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"对话级变量 {var_name} 数据损坏，将从数据库删除: {e}")
                    await self._delete_corrupted_variable(doc)
                    corrupted_count += 1
            
            if corrupted_count > 0:
                logger.info(f"对话 {flow_id} 加载变量完成: 成功 {loaded_count} 个，清理损坏数据 {corrupted_count} 个")
            else:
                logger.debug(f"对话 {flow_id} 加载变量完成: {loaded_count} 个")
            
        except Exception as e:
            logger.error(f"加载对话级所有变量失败: {e}")

    async def _delete_corrupted_variable(self, doc: Dict[str, Any]):
        """删除损坏的变量数据
        
        Args:
            doc: 损坏的变量文档
        """
        try:
            collection = MongoDB().get_collection("variables")
            
            # 记录损坏的数据用于分析
            corrupted_collection = MongoDB().get_collection("corrupted_variables")
            backup_doc = doc.copy()
            backup_doc["corrupted_at"] = datetime.now(UTC)
            backup_doc["reason"] = "deserialization_failed"
            
            # 备份损坏数据
            try:
                await corrupted_collection.insert_one(backup_doc)
            except Exception as backup_e:
                logger.warning(f"备份损坏变量数据失败: {backup_e}")
            
            # 删除原始损坏数据
            if "_id" in doc:
                result = await collection.delete_one({"_id": doc["_id"]})
                if result.deleted_count > 0:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.debug(f"已删除损坏的变量数据: {var_name}")
                else:
                    logger.warning(f"未能删除损坏的变量数据，可能已被删除")
            
        except Exception as e:
            logger.error(f"删除损坏变量数据失败: {e}")
            # 即使删除失败也不抛出异常，避免影响其他变量的加载

    async def cleanup_corrupted_variables(self) -> Dict[str, int]:
        """手动清理所有损坏的变量数据
        
        Returns:
            Dict[str, int]: 清理统计信息 {"checked": 检查数量, "cleaned": 清理数量}
        """
        logger.info("开始检查和清理损坏的变量数据...")
        
        collection = MongoDB().get_collection("variables")
        checked_count = 0
        cleaned_count = 0
        
        try:
            # 遍历所有变量进行检查
            cursor = collection.find({})
            
            async for doc in cursor:
                checked_count += 1
                try:
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        # 找到对应的变量类并尝试反序列化
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                var_class.deserialize(doc)  # 只是测试反序列化，不保存
                                break
                    else:
                        # 未知的变量类型也视为损坏
                        raise ValueError(f"未知的变量类型: {variable_class_name}")
                        
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"发现损坏的变量 {var_name}，将删除: {e}")
                    await self._delete_corrupted_variable(doc)
                    cleaned_count += 1
            
            result = {"checked": checked_count, "cleaned": cleaned_count}
            logger.info(f"变量数据清理完成: 检查了 {checked_count} 个变量，清理了 {cleaned_count} 个损坏的变量")
            return result
            
        except Exception as e:
            logger.error(f"清理损坏变量失败: {e}")
            return {"checked": checked_count, "cleaned": cleaned_count}
    
    async def get_corrupted_variables_info(self) -> List[Dict[str, Any]]:
        """获取已备份的损坏变量信息
        
        Returns:
            List[Dict[str, Any]]: 损坏变量信息列表
        """
        try:
            corrupted_collection = MongoDB().get_collection("corrupted_variables")
            corrupted_vars = []
            
            cursor = corrupted_collection.find({}).sort("corrupted_at", -1).limit(100)
            async for doc in cursor:
                var_info = {
                    "name": doc.get("metadata", {}).get("name", "unknown"),
                    "scope": doc.get("metadata", {}).get("scope", "unknown"),
                    "var_type": doc.get("metadata", {}).get("var_type", "unknown"),
                    "corrupted_at": doc.get("corrupted_at"),
                    "reason": doc.get("reason", "unknown"),
                    "user_sub": doc.get("metadata", {}).get("user_sub"),
                    "flow_id": doc.get("metadata", {}).get("flow_id"),
                }
                corrupted_vars.append(var_info)
            
            return corrupted_vars
            
        except Exception as e:
            logger.error(f"获取损坏变量信息失败: {e}")
            return []


# 全局变量池实例
_variable_pool = None


async def get_variable_pool() -> VariablePool:
    """获取全局变量池实例"""
    global _variable_pool
    if _variable_pool is None:
        _variable_pool = VariablePool()
        await _variable_pool.initialize()
    return _variable_pool 