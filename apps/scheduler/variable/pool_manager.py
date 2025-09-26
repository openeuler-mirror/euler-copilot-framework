import logging
import asyncio
from typing import Dict, List, Optional, Set, Tuple, Any
from contextlib import asynccontextmanager

from apps.common.mongo import MongoDB
from .pool_base import (
    BaseVariablePool, 
    UserVariablePool, 
    FlowVariablePool, 
    ConversationVariablePool
)
from .type import VariableScope
from .base import BaseVariable

logger = logging.getLogger(__name__)


class VariablePoolManager:
    """变量池管理器 - 管理所有类型变量池的生命周期"""
    
    def __init__(self):
        """初始化变量池管理器"""
        # 用户变量池缓存: user_id -> UserVariablePool
        self._user_pools: Dict[str, UserVariablePool] = {}
        
        # 流程变量池缓存: flow_id -> FlowVariablePool
        self._flow_pools: Dict[str, FlowVariablePool] = {}
        
        # 对话变量池缓存: conversation_id -> ConversationVariablePool
        self._conversation_pools: Dict[str, ConversationVariablePool] = {}
        
        # 对话模板池缓存: flow_id -> ConversationVariablePool
        self._conversation_template_pools: Dict[str, ConversationVariablePool] = {}
        
        # 流程继承关系缓存: child_flow_id -> parent_flow_id
        self._flow_inheritance: Dict[str, str] = {}
        
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """初始化变量池管理器"""
        async with self._lock:
            if not self._initialized:
                await self._load_existing_entities()
                await self._patrol_and_create_missing_pools()
                self._initialized = True
                logger.info("变量池管理器初始化完成")
    
    async def _load_existing_entities(self):
        """加载现有的用户和流程实体"""
        try:
            # 这里应该从相应的用户和流程数据库表中加载
            # 目前先从变量表中推断存在的实体
            collection = MongoDB().get_collection("variables")
            
            # 获取所有唯一的用户ID
            user_ids = await collection.distinct("metadata.user_sub", {
                "metadata.user_sub": {"$ne": None}
            })
            logger.info(f"发现 {len(user_ids)} 个用户需要变量池")
            
            # 获取所有唯一的流程ID
            flow_ids = await collection.distinct("metadata.flow_id", {
                "metadata.flow_id": {"$ne": None}
            })
            logger.info(f"发现 {len(flow_ids)} 个流程需要变量池")
            
            # 缓存实体信息用于后续创建池
            self._discovered_users = set(user_ids)
            self._discovered_flows = set(flow_ids)
            
        except Exception as e:
            logger.error(f"加载现有实体失败: {e}")
            self._discovered_users = set()
            self._discovered_flows = set()
    
    async def _patrol_and_create_missing_pools(self):
        """巡检并创建缺失的变量池"""
        logger.info("开始巡检并创建缺失的变量池...")
        
        # 为所有发现的用户创建用户变量池
        created_user_pools = 0
        for user_id in self._discovered_users:
            if user_id not in self._user_pools:
                await self._create_user_pool(user_id)
                created_user_pools += 1
        
        # 为所有发现的流程创建流程变量池
        created_flow_pools = 0
        for flow_id in self._discovered_flows:
            if flow_id not in self._flow_pools:
                await self._create_flow_pool(flow_id)
                created_flow_pools += 1
        
        logger.info(f"巡检完成: 创建了 {created_user_pools} 个用户池, "
                   f"{created_flow_pools} 个流程池")
    
    async def get_user_pool(self, user_id: str, auto_create: bool = True) -> Optional[UserVariablePool]:
        """获取用户变量池"""
        if user_id in self._user_pools:
            return self._user_pools[user_id]
        
        if auto_create:
            return await self._create_user_pool(user_id)
        
        return None
    
    async def get_flow_pool(self, flow_id: str, parent_flow_id: Optional[str] = None, 
                           auto_create: bool = True) -> Optional[FlowVariablePool]:
        """获取流程变量池"""
        # 使用锁避免竞态条件
        async with self._lock:
            if flow_id in self._flow_pools:
                return self._flow_pools[flow_id]
            
            if auto_create:
                return await self._create_flow_pool(flow_id, parent_flow_id)
        
        return None
    
    async def create_conversation_pool(self, conversation_id: str, flow_id: str) -> ConversationVariablePool:
        """创建对话变量池（包含系统变量和对话变量）"""
        # 使用锁避免竞态条件
        async with self._lock:
            # 检查是否已经存在
            if conversation_id in self._conversation_pools:
                existing_pool = self._conversation_pools[conversation_id]
                logger.info(f"对话池 {conversation_id} 已存在，直接返回")
                return existing_pool
        
            # 创建对话变量池对象（但不初始化）
            conversation_pool = ConversationVariablePool(conversation_id, flow_id)
            
            # 先缓存池，避免其他请求重复创建
            self._conversation_pools[conversation_id] = conversation_pool
            
            logger.info(f"已创建对话变量池对象: {conversation_id}")
        
        # 🔑 重要修复：在锁外进行初始化，避免死锁
        try:
            # 初始化池（在锁外进行，避免嵌套锁）
            await conversation_pool.initialize()
        
            # 从对话模板池继承变量（如果存在）
            conversation_template_pool = await self._get_conversation_template_pool(flow_id)
            await conversation_pool.inherit_from_conversation_template(conversation_template_pool)
        
            logger.info(f"对话变量池初始化完成: {conversation_id}")
            return conversation_pool
            
        except Exception as e:
            # 如果初始化失败，从缓存中移除
            async with self._lock:
                if conversation_id in self._conversation_pools:
                    del self._conversation_pools[conversation_id]
            logger.error(f"对话变量池初始化失败: {conversation_id} - {e}")
            raise
    
    async def get_conversation_pool(self, conversation_id: str) -> Optional[ConversationVariablePool]:
        """获取对话变量池"""
        return self._conversation_pools.get(conversation_id)
    
    async def remove_conversation_pool(self, conversation_id: str) -> bool:
        """移除对话变量池"""
        if conversation_id in self._conversation_pools:
            del self._conversation_pools[conversation_id]
            logger.info(f"已移除对话变量池: {conversation_id}")
            return True
        return False
    
    async def get_variable_from_any_pool(self, 
                                       name: str, 
                                       scope: VariableScope,
                                       user_id: Optional[str] = None,
                                       flow_id: Optional[str] = None,
                                       conversation_id: Optional[str] = None) -> Optional[BaseVariable]:
        """从任意池中获取变量"""
        if scope == VariableScope.USER and user_id:
            pool = await self.get_user_pool(user_id)
            return await pool.get_variable(name) if pool else None
        
        elif scope == VariableScope.ENVIRONMENT and flow_id:
            pool = await self.get_flow_pool(flow_id)
            return await pool.get_variable(name) if pool else None
        
        elif scope == VariableScope.CONVERSATION:
            if conversation_id:
                # 使用conversation_id查询对话变量实例
                pool = await self.get_conversation_pool(conversation_id)
                return await pool.get_variable(name) if pool else None
            elif flow_id:
                # 使用flow_id查询对话变量模板
                flow_pool = await self.get_flow_pool(flow_id)
                if flow_pool:
                    return await flow_pool.get_conversation_template(name)
            return None
        
        # 系统变量处理
        elif scope == VariableScope.SYSTEM:
            if conversation_id:
                # 优先使用conversation_id查询实际的系统变量实例
                pool = await self.get_conversation_pool(conversation_id)
                if pool:
                    variable = await pool.get_variable(name)
                    # 检查是否为系统变量
                    if variable and hasattr(variable.metadata, 'is_system') and variable.metadata.is_system:
                        return variable
            elif flow_id:
                # 使用flow_id查询系统变量模板
                flow_pool = await self.get_flow_pool(flow_id)
                if flow_pool:
                    return await flow_pool.get_system_template(name)
        
        return None
    
    async def list_variables_from_any_pool(self,
                                         scope: VariableScope,
                                         user_id: Optional[str] = None,
                                         flow_id: Optional[str] = None,
                                         conversation_id: Optional[str] = None) -> List[BaseVariable]:
        """从任意池中列出变量"""
        if scope == VariableScope.USER and user_id:
            pool = await self.get_user_pool(user_id)
            return await pool.list_variables() if pool else []
        
        elif scope == VariableScope.ENVIRONMENT and flow_id:
            pool = await self.get_flow_pool(flow_id)
            return await pool.list_variables() if pool else []
        
        elif scope == VariableScope.CONVERSATION:
            if conversation_id:
                # 使用conversation_id查询对话变量实例
                pool = await self.get_conversation_pool(conversation_id)
                if pool:
                    # 只返回非系统变量
                    return await pool.list_variables(include_system=False)
            elif flow_id:
                # 使用flow_id查询对话变量模板
                flow_pool = await self.get_flow_pool(flow_id)
                if flow_pool:
                    return await flow_pool.list_conversation_templates()
            return []
        
        # 系统变量处理
        elif scope == VariableScope.SYSTEM:
            if conversation_id:
                # 优先使用conversation_id查询实际的系统变量实例
                pool = await self.get_conversation_pool(conversation_id)
                if pool:
                    # 只返回系统变量
                    return await pool.list_system_variables()
            elif flow_id:
                # 使用flow_id查询系统变量模板
                flow_pool = await self.get_flow_pool(flow_id)
                if flow_pool:
                    return await flow_pool.list_system_templates()
            return []
        
        return []
    
    async def update_system_variable(self, conversation_id: str, name: str, value: Any) -> bool:
        """更新对话中的系统变量"""
        conversation_pool = await self.get_conversation_pool(conversation_id)
        if conversation_pool:
            return await conversation_pool.update_system_variable(name, value)
        return False
    
    async def _create_user_pool(self, user_id: str) -> UserVariablePool:
        """创建用户变量池"""
        pool = UserVariablePool(user_id)
        await pool.initialize()
        self._user_pools[user_id] = pool
        logger.info(f"已创建用户变量池: {user_id}")
        return pool
    
    async def _create_flow_pool(self, flow_id: str, parent_flow_id: Optional[str] = None) -> FlowVariablePool:
        """创建流程变量池"""
        pool = FlowVariablePool(flow_id, parent_flow_id)
        await pool.initialize()
        
        # 如果有父流程，从父流程继承变量
        if parent_flow_id and parent_flow_id in self._flow_pools:
            parent_pool = self._flow_pools[parent_flow_id]
            await pool.inherit_from_parent(parent_pool)
            self._flow_inheritance[flow_id] = parent_flow_id
        
        self._flow_pools[flow_id] = pool
        logger.info(f"已创建流程变量池: {flow_id}")
        return pool
    
    async def _get_conversation_template_pool(self, flow_id: str) -> Optional[ConversationVariablePool]:
        """获取对话模板池 - 从MongoDB加载对应flow_id的对话变量模板"""
        try:
            # 检查缓存
            if flow_id in self._conversation_template_pools:
                logger.debug(f"从缓存获取对话模板池: {flow_id}")
                return self._conversation_template_pools[flow_id]
            
            # 从MongoDB查询对话变量模板 (只查询is_template=True的)
            collection = MongoDB().get_collection("variables")
            cursor = collection.find({
                "metadata.scope": VariableScope.CONVERSATION.value,
                "metadata.flow_id": flow_id,
                "metadata.is_template": True
            })
            
            # 加载对话变量模板
            template_variables = []
            async for doc in cursor:
                try:
                    # 从VARIABLE_CLASS_MAP导入
                    from .variables import VARIABLE_CLASS_MAP
                    
                    variable_class_name = doc.get("class")
                    if variable_class_name in [cls.__name__ for cls in VARIABLE_CLASS_MAP.values()]:
                        for var_class in VARIABLE_CLASS_MAP.values():
                            if var_class.__name__ == variable_class_name:
                                variable = var_class.deserialize(doc)
                                template_variables.append(variable)
                                break
                except Exception as e:
                    var_name = doc.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"对话变量模板 {var_name} 数据损坏: {e}")
            
            # 如果没有找到对话变量模板，返回None
            if not template_variables:
                logger.debug(f"流程 {flow_id} 没有找到对话变量模板")
                return None
            
            # 创建对话模板池，使用特殊的模板conversation_id
            template_conversation_id = f"template_{flow_id}"
            template_pool = ConversationVariablePool(template_conversation_id, flow_id)
            
            # 手动初始化池的基础结构（不调用完整的initialize，避免从数据库重复加载）
            template_pool._variables = {}
            template_pool._initialized = True
            
            # 将模板变量加载到池中
            for variable in template_variables:
                template_pool._variables[variable.name] = variable
            
            # 缓存模板池
            self._conversation_template_pools[flow_id] = template_pool
            
            logger.info(f"已为流程 {flow_id} 创建对话模板池，包含 {len(template_variables)} 个变量模板")
            return template_pool
            
        except Exception as e:
            logger.error(f"获取对话模板池失败 (flow_id: {flow_id}): {e}")
        return None
    
    def clear_conversation_template_cache(self, flow_id: str):
        """清除对话模板池缓存 - 当模板更新时调用"""
        if flow_id in self._conversation_template_pools:
            del self._conversation_template_pools[flow_id]
            logger.info(f"已清除对话模板池缓存: {flow_id}")
    
    async def clear_conversation_variables(self, flow_id: str):
        """清空工作流的所有对话变量池"""
        to_remove = []
        for conversation_id, pool in self._conversation_pools.items():
            if pool.flow_id == flow_id:
                to_remove.append(conversation_id)
        
        for conversation_id in to_remove:
            del self._conversation_pools[conversation_id]
        
        logger.info(f"已清空工作流 {flow_id} 的 {len(to_remove)} 个对话变量池")
    
    async def reset_conversation_variables_to_defaults(self, conversation_id: str) -> bool:
        """将指定对话的变量重置为Flow定义的默认值
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 是否重置成功
        """
        try:
            conversation_pool = await self.get_conversation_pool(conversation_id)
            if not conversation_pool:
                logger.warning(f"[VariablePoolManager] 未找到对话变量池: {conversation_id}")
                return False
            
            flow_id = conversation_pool.flow_id
            flow_pool = await self.get_flow_pool(flow_id)
            if not flow_pool:
                logger.warning(f"[VariablePoolManager] 未找到Flow变量池: {flow_id}")
                return False
            
            # 获取所有对话变量模板
            conversation_templates = await flow_pool.list_conversation_templates()
            if not conversation_templates:
                logger.info(f"[VariablePoolManager] Flow {flow_id} 没有定义对话变量模板，无需重置")
                return True
            
            reset_count = 0
            failed_count = 0
            
            # 重置每个对话变量到其默认值
            for template in conversation_templates:
                try:
                    existing_variable = await conversation_pool.get_variable(template.name)
                    if existing_variable:
                        # 跳过系统变量
                        if hasattr(existing_variable.metadata, 'is_system') and existing_variable.metadata.is_system:
                            continue
                        
                        # 重置为模板的默认值
                        await conversation_pool.update_variable(
                            name=template.name,
                            value=template.value,
                            force_system_update=False
                        )
                        reset_count += 1
                        logger.debug(f"[VariablePoolManager] 已重置对话变量: {template.name} = {template.value}")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"[VariablePoolManager] 重置对话变量 {template.name} 失败: {e}")
            
            if reset_count > 0:
                logger.info(f"[VariablePoolManager] 对话 {conversation_id} 成功重置了 {reset_count} 个变量到默认值")
            
            return failed_count == 0
            
        except Exception as e:
            logger.error(f"[VariablePoolManager] 重置对话变量池失败: conversation_id={conversation_id}, 错误: {e}")
            return False
    
    async def get_pool_stats(self) -> Dict[str, int]:
        """获取变量池统计信息"""
        return {
            "user_pools": len(self._user_pools),
            "flow_pools": len(self._flow_pools),
            "conversation_pools": len(self._conversation_pools),
        }
    
    async def cleanup_unused_pools(self, active_conversations: Set[str]):
        """清理未使用的对话变量池"""
        to_remove = []
        for conversation_id in self._conversation_pools:
            if conversation_id not in active_conversations:
                to_remove.append(conversation_id)
        
        # 🔑 增强：在移除池之前清理文件资源
        for conversation_id in to_remove:
            try:
                pool = self._conversation_pools[conversation_id]
                await self._cleanup_conversation_files(pool)
            except Exception as e:
                logger.error(f"清理对话 {conversation_id} 的文件资源失败: {e}")
            finally:
                del self._conversation_pools[conversation_id]
        
        if to_remove:
            logger.info(f"清理了 {len(to_remove)} 个未使用的对话变量池")
    
    async def _cleanup_conversation_files(self, pool) -> None:
        """清理对话池中的文件资源"""
        try:
            from .type import VariableType
            from apps.services.document import DocumentManager
            
            variables = await pool.list_variables()
            file_ids_to_cleanup = []
            user_id = None
            
            for variable in variables:
                # 记录用户ID用于文件清理
                if not user_id and hasattr(variable.metadata, 'created_by'):
                    user_id = variable.metadata.created_by
                
                if variable.metadata.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                    if isinstance(variable.value, dict):
                        if variable.metadata.var_type == VariableType.FILE:
                            file_id = variable.value.get("file_id")
                            if file_id:
                                file_ids_to_cleanup.append(file_id)
                        else:  # ARRAY_FILE
                            file_ids = variable.value.get("file_ids", [])
                            file_ids_to_cleanup.extend(file_ids)
            
            # 批量删除文件
            if file_ids_to_cleanup and user_id:
                await DocumentManager.delete_document(user_id, file_ids_to_cleanup)
                logger.info(f"已清理对话池 {pool.pool_id} 中的 {len(file_ids_to_cleanup)} 个文件")
            elif file_ids_to_cleanup:
                logger.warning(f"对话池 {pool.pool_id} 中有 {len(file_ids_to_cleanup)} 个文件无法清理（缺少用户ID）")
                
        except Exception as e:
            logger.error(f"清理对话池文件失败: {e}")
    
    @asynccontextmanager
    async def get_pool_for_scope(self, 
                                scope: VariableScope,
                                user_id: Optional[str] = None,
                                flow_id: Optional[str] = None,
                                conversation_id: Optional[str] = None):
        """上下文管理器，获取指定作用域的变量池"""
        pool = None
        
        try:
            if scope == VariableScope.USER and user_id:
                pool = await self.get_user_pool(user_id)
            elif scope == VariableScope.ENVIRONMENT and flow_id:
                pool = await self.get_flow_pool(flow_id)
            elif scope in [VariableScope.CONVERSATION, VariableScope.SYSTEM] and conversation_id:
                pool = await self.get_conversation_pool(conversation_id)
            
            if not pool:
                raise ValueError(f"无法获取 {scope.value} 级变量池")
            
            yield pool
            
        except Exception:
            raise
        finally:
            # 这里可以添加清理逻辑，比如对话池的自动清理等
            pass


# 全局变量池管理器实例
_pool_manager = None


async def get_pool_manager() -> VariablePoolManager:
    """获取全局变量池管理器实例"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = VariablePoolManager()
        await _pool_manager.initialize()
    return _pool_manager


async def initialize_pool_manager():
    """初始化变量池管理器（在应用启动时调用）"""
    await get_pool_manager()
    logger.info("变量池管理器已启动") 