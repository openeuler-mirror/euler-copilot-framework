# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""前置节点变量预解析缓存服务"""

import asyncio
import hashlib
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

from apps.common.redis_cache import RedisCache
from apps.common.process_handler import ProcessHandler
from apps.services.flow import FlowManager
from apps.scheduler.variable.variables import create_variable
from apps.scheduler.variable.base import VariableMetadata
from apps.scheduler.variable.type import VariableType, VariableScope

logger = logging.getLogger(__name__)

# 全局Redis缓存实例
redis_cache = RedisCache()
predecessor_cache = None

# 添加任务管理
_background_tasks: Dict[str, asyncio.Task] = {}
_task_lock = asyncio.Lock()

def _get_predecessor_cache():
    """获取predecessor_cache实例，确保初始化"""
    global predecessor_cache
    if predecessor_cache is None:
        from apps.common.redis_cache import PredecessorVariableCache
        predecessor_cache = PredecessorVariableCache(redis_cache)
    return predecessor_cache

async def init_predecessor_cache():
    """初始化前置节点变量缓存"""
    global predecessor_cache
    if predecessor_cache is None:
        from apps.common.redis_cache import PredecessorVariableCache
        predecessor_cache = PredecessorVariableCache(redis_cache)

async def cleanup_background_tasks():
    """清理后台任务"""
    async with _task_lock:
        if not _background_tasks:
            logger.info("没有后台任务需要清理")
            return
            
        logger.info(f"开始清理 {len(_background_tasks)} 个后台任务")
        
        # 取消所有未完成的任务
        cancelled_count = 0
        for task_id, task in list(_background_tasks.items()):
            if not task.done():
                task.cancel()
                cancelled_count += 1
                logger.debug(f"取消后台任务: {task_id}")
        
        # 等待任务取消完成，设置超时避免永久等待
        if cancelled_count > 0:
            logger.info(f"等待 {cancelled_count} 个任务取消完成...")
            timeout = 5.0  # 5秒超时
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[task for task in _background_tasks.values()], return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"等待任务取消超时 ({timeout}s)，强制清理")
            except Exception as e:
                logger.error(f"等待任务取消时出错: {e}")
        
        # 清理任务字典
        completed_count = len(_background_tasks)
        _background_tasks.clear()
        logger.info(f"后台任务清理完成，共清理 {completed_count} 个任务")

async def periodic_cleanup_background_tasks():
    """定期清理已完成的后台任务"""
    try:
        async with _task_lock:
            if not _background_tasks:
                return
            
            completed_tasks = []
            for task_id, task in list(_background_tasks.items()):
                if task.done():
                    completed_tasks.append(task_id)
                    try:
                        # 获取任务结果，记录异常
                        await task
                        logger.debug(f"后台任务已完成: {task_id}")
                    except Exception as e:
                        logger.error(f"后台任务执行异常: {task_id}, 错误: {e}")
            
            # 移除已完成的任务
            for task_id in completed_tasks:
                _background_tasks.pop(task_id, None)
            
            if completed_tasks:
                logger.info(f"定期清理了 {len(completed_tasks)} 个已完成的后台任务")
                
    except Exception as e:
        logger.error(f"定期清理后台任务失败: {e}")


class PredecessorCacheService:
    """前置节点变量预解析缓存服务"""
    
    @staticmethod
    async def initialize_redis():
        """初始化Redis连接"""
        try:
            # 从配置文件读取Redis配置
            from apps.common.config import Config
            
            config = Config().get_config()
            redis_config = config.redis
            
            logger.info(f"准备连接Redis: {redis_config.host}:{redis_config.port}")
            await redis_cache.init(redis_config=redis_config)
            
            # 验证连接是否正常
            if redis_cache.is_connected():
                logger.info("前置节点缓存服务Redis初始化成功")
                return
            else:
                raise Exception("Redis连接验证失败")
                
        except Exception as e:
            logger.error(f"使用配置文件连接Redis失败: {e}")
            
            # 尝试降级连接方案
            try:
                logger.info("尝试降级连接方案...")
                from apps.common.config import Config
                config = Config().get_config()
                redis_config = config.redis
                
                # 构建简单的Redis URL
                password_part = f":{redis_config.password}@" if redis_config.password else ""
                redis_url = f"redis://{password_part}{redis_config.host}:{redis_config.port}/{redis_config.database}"
                
                await redis_cache.init(redis_url=redis_url)
                
                if redis_cache.is_connected():
                    logger.info("降级连接方案成功")
                    return
                else:
                    raise Exception("降级连接方案也失败")
                    
            except Exception as fallback_error:
                logger.error(f"降级连接方案也失败: {fallback_error}")
                
            # 即使Redis初始化失败，也不要抛出异常，而是继续运行（降级模式）
            logger.info("将使用实时解析模式作为降级方案")
    
    @staticmethod
    def calculate_flow_hash(flow_item) -> str:
        """计算Flow拓扑结构的哈希值"""
        try:
            # 提取关键的拓扑信息
            topology_data = {
                'nodes': [
                    {
                        'step_id': node.step_id,
                        'call_id': getattr(node, 'call_id', ''),
                        'parameters': getattr(node, 'parameters', {})
                    }
                    for node in flow_item.nodes
                ],
                'edges': [
                    {
                        'source_node': edge.source_node,
                        'target_node': edge.target_node
                    }
                    for edge in flow_item.edges
                ]
            }
            
            # 生成哈希
            topology_json = json.dumps(topology_data, sort_keys=True)
            return hashlib.md5(topology_json.encode()).hexdigest()
        except Exception as e:
            logger.error(f"计算Flow哈希失败: {e}")
            return str(datetime.now(UTC).timestamp())  # 降级方案
    
    @staticmethod
    async def trigger_flow_parsing(flow_id: str, force_refresh: bool = False):
        """触发整个Flow的前置节点变量解析"""
        try:
            # 获取Flow信息
            flow_item = await PredecessorCacheService._get_flow_by_flow_id(flow_id)
            if not flow_item:
                logger.warning(f"Flow不存在，跳过解析: {flow_id}")
                return
            
            # 计算当前Flow的哈希
            current_hash = PredecessorCacheService.calculate_flow_hash(flow_item)
            
            # 检查是否需要重新解析
            if not force_refresh:
                cached_hash = await _get_predecessor_cache().get_flow_hash(flow_id)
                if cached_hash == current_hash:
                    logger.info(f"Flow拓扑未变化，跳过解析: {flow_id}")
                    return
            
            # 更新Flow哈希
            await _get_predecessor_cache().set_flow_hash(flow_id, current_hash)
            
            # 清除旧缓存
            await _get_predecessor_cache().invalidate_flow_cache(flow_id)
            
            # 为每个节点启动异步解析任务
            tasks = []
            for node in flow_item.nodes:
                step_id = node.step_id
                task_id = f"parse_predecessor_{flow_id}_{step_id}"
                
                # 避免重复任务
                async with _task_lock:
                    if task_id in _background_tasks and not _background_tasks[task_id].done():
                        continue
                        
                    # 异步启动解析任务
                    task = asyncio.create_task(
                        PredecessorCacheService._parse_single_node_predecessor(
                            flow_id, step_id, current_hash
                        )
                    )
                    _background_tasks[task_id] = task
                    tasks.append((task_id, task))
            
            if tasks:
                logger.info(f"启动Flow前置节点解析任务: {flow_id}, 节点数量: {len(tasks)}")
                # 简化处理：直接启动任务，依赖cleanup_background_tasks进行清理
                for task_id, task in tasks:
                    # 不添加回调，让任务自然完成
                    logger.debug(f"启动后台任务: {task_id}")
            
        except Exception as e:
            logger.error(f"触发Flow解析失败: {flow_id}, 错误: {e}")

    @staticmethod
    async def _cleanup_task(task_id: str):
        """清理完成的任务"""
        try:
            async with _task_lock:
                task = _background_tasks.pop(task_id, None)
                if task and task.done():
                    # 检查任务是否有异常
                    try:
                        result = await task
                        logger.debug(f"后台任务完成: {task_id}")
                    except Exception as e:
                        logger.error(f"后台任务执行异常: {task_id}, 错误: {e}")
        except Exception as e:
            logger.error(f"清理任务失败: {task_id}, 错误: {e}")

    @staticmethod
    async def _parse_single_node_predecessor(flow_id: str, step_id: str, flow_hash: str):
        """解析单个节点的前置节点变量"""
        try:
            # 检查事件循环是否仍然活跃
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                logger.warning(f"事件循环已关闭，跳过解析: {flow_id}:{step_id}")
                return
            
            # 设置解析状态
            await _get_predecessor_cache().set_parsing_status(flow_id, step_id, "parsing")
            
            # 获取Flow信息
            flow_item = await PredecessorCacheService._get_flow_by_flow_id(flow_id)
            if not flow_item:
                await _get_predecessor_cache().set_parsing_status(flow_id, step_id, "failed")
                return
            
            # 查找前置节点
            predecessor_nodes = PredecessorCacheService._find_predecessor_nodes(flow_item, step_id)
            
            # 为每个前置节点创建输出变量
            variables_data = []
            for node in predecessor_nodes:
                node_vars = await PredecessorCacheService._create_node_output_variables(node)
                variables_data.extend(node_vars)
            
            # 缓存结果
            await _get_predecessor_cache().set_cached_variables(flow_id, step_id, variables_data, flow_hash)
            
            # 设置完成状态
            await _get_predecessor_cache().set_parsing_status(flow_id, step_id, "completed")
            
            logger.info(f"节点前置变量解析完成: {flow_id}:{step_id}, 变量数量: {len(variables_data)}")
            
        except asyncio.CancelledError:
            logger.info(f"节点前置变量解析任务被取消: {flow_id}:{step_id}")
            try:
                await _get_predecessor_cache().set_parsing_status(flow_id, step_id, "cancelled")
            except Exception:
                pass  # 忽略清理时的错误
        except Exception as e:
            logger.error(f"解析节点前置变量失败: {flow_id}:{step_id}, 错误: {e}")
            try:
                await _get_predecessor_cache().set_parsing_status(flow_id, step_id, "failed")
            except Exception:
                # 如果连设置状态都失败了，说明可能是事件循环关闭导致的
                logger.warning(f"无法设置解析状态为失败: {flow_id}:{step_id}")
    
    @staticmethod
    async def get_predecessor_variables_optimized(
        flow_id: str, 
        step_id: str, 
        user_sub: str,
        max_wait_time: int = 10
    ) -> List[Dict[str, Any]]:
        """优化的前置节点变量获取（优先使用缓存）"""
        try:
            # 1. 先尝试从缓存获取
            cached_vars = await _get_predecessor_cache().get_cached_variables(flow_id, step_id)
            if cached_vars is not None:
                logger.info(f"使用缓存的前置节点变量: {flow_id}:{step_id}")
                return cached_vars
            
            # 2. 检查是否正在解析中
            if await _get_predecessor_cache().is_parsing_in_progress(flow_id, step_id):
                logger.info(f"等待前置节点变量解析完成: {flow_id}:{step_id}")
                # 等待解析完成
                if await _get_predecessor_cache().wait_for_parsing_completion(flow_id, step_id, max_wait_time):
                    cached_vars = await _get_predecessor_cache().get_cached_variables(flow_id, step_id)
                    if cached_vars is not None:
                        return cached_vars
            
            # 3. 缓存未命中，启动实时解析
            logger.info(f"缓存未命中，启动实时解析: {flow_id}:{step_id}")
            
            # 获取Flow信息
            flow_item = await PredecessorCacheService._get_flow_by_flow_id(flow_id)
            if not flow_item:
                return []
            
            # 计算Flow哈希
            flow_hash = PredecessorCacheService.calculate_flow_hash(flow_item)
            
            # 立即解析并缓存
            await PredecessorCacheService._parse_single_node_predecessor(flow_id, step_id, flow_hash)
            
            # 再次尝试从缓存获取
            cached_vars = await _get_predecessor_cache().get_cached_variables(flow_id, step_id)
            return cached_vars or []
            
        except Exception as e:
            logger.error(f"获取优化前置节点变量失败: {flow_id}:{step_id}, 错误: {e}")
            return []
    
    @staticmethod
    async def _get_flow_by_flow_id(flow_id: str):
        """通过flow_id获取工作流信息"""
        try:
            from apps.common.mongo import MongoDB
            
            app_collection = MongoDB().get_collection("app")
            
            # 查询包含此flow_id的app，同时获取app_id
            app_record = await app_collection.find_one(
                {"flows.id": flow_id},
                {"_id": 1}
            )
            
            if not app_record:
                logger.warning(f"未找到包含flow_id {flow_id} 的应用")
                return None
                
            app_id = app_record["_id"]
            
            # 使用现有的FlowManager方法获取flow
            flow_item = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
            return flow_item
            
        except Exception as e:
            logger.error(f"通过flow_id获取工作流失败: {e}")
            return None
    
    @staticmethod
    def _find_predecessor_nodes(flow_item, current_step_id: str) -> List:
        """在工作流中查找所有前置节点（使用BFS算法直到start节点）"""
        try:
            from collections import deque
            
            predecessor_nodes = []
            visited = set()  # 避免重复访问节点
            queue = deque([current_step_id])  # BFS队列
            visited.add(current_step_id)
            
            # 构建边的反向映射，便于快速查找前置节点
            reverse_edges = {}  # target_node -> [source_node1, source_node2, ...]
            for edge in flow_item.edges:
                if edge.target_node not in reverse_edges:
                    reverse_edges[edge.target_node] = []
                reverse_edges[edge.target_node].append(edge.source_node)
            
            # 构建节点ID到节点对象的映射
            node_map = {node.step_id: node for node in flow_item.nodes}
            
            # BFS遍历找到所有前置节点
            while queue:
                current_node_id = queue.popleft()
                
                # 获取当前节点的直接前置节点
                if current_node_id in reverse_edges:
                    for source_node_id in reverse_edges[current_node_id]:
                        if source_node_id not in visited:
                            visited.add(source_node_id)
                            queue.append(source_node_id)
                            
                            # 将前置节点添加到结果中（排除当前节点本身）
                            if source_node_id != current_step_id:
                                source_node = node_map.get(source_node_id)
                                if source_node:
                                    predecessor_nodes.append(source_node)
            
            logger.debug(f"为节点 {current_step_id} 找到 {len(predecessor_nodes)} 个前置节点: {[node.step_id for node in predecessor_nodes]}")
            return predecessor_nodes
            
        except Exception as e:
            logger.error(f"查找前置节点失败: {e}")
            return []
    
    @staticmethod
    async def _create_node_output_variables(node) -> List[Dict[str, Any]]:
        """根据节点的output_parameters配置创建输出变量数据"""
        try:
            variables_data = []
            node_id = node.step_id
            
            # 统一从节点的output_parameters创建变量
            output_params = {}
            if hasattr(node, 'parameters') and node.parameters:
                if isinstance(node.parameters, dict):
                    output_params = node.parameters.get('output_parameters', {})
                else:
                    output_params = getattr(node.parameters, 'output_parameters', {})
            
            # 如果没有配置output_parameters，跳过此节点
            if not output_params:
                logger.debug(f"节点 {node_id} 没有配置output_parameters，跳过创建输出变量")
                return variables_data
            
            # 遍历output_parameters中的每个key-value对，创建对应的变量数据
            for param_name, param_config in output_params.items():
                # 解析参数配置
                if isinstance(param_config, dict):
                    param_type = param_config.get('type', 'string')
                    description = param_config.get('description', '')
                else:
                    # 如果param_config不是字典，可能是简单的类型字符串
                    param_type = str(param_config) if param_config else 'string'
                    description = ''
                
                # 确定变量类型
                var_type = VariableType.STRING  # 默认类型
                if param_type == 'number':
                    var_type = VariableType.NUMBER
                elif param_type == 'boolean':
                    var_type = VariableType.BOOLEAN
                elif param_type == 'object':
                    var_type = VariableType.OBJECT
                elif param_type == 'array' or param_type == 'array[any]':
                    var_type = VariableType.ARRAY_ANY
                elif param_type == 'array[string]':
                    var_type = VariableType.ARRAY_STRING
                elif param_type == 'array[number]':
                    var_type = VariableType.ARRAY_NUMBER
                elif param_type == 'array[object]':
                    var_type = VariableType.ARRAY_OBJECT
                elif param_type == 'array[boolean]':
                    var_type = VariableType.ARRAY_BOOLEAN
                elif param_type == 'array[file]':
                    var_type = VariableType.ARRAY_FILE
                elif param_type == 'array[secret]':
                    var_type = VariableType.ARRAY_SECRET
                elif param_type == 'file':
                    var_type = VariableType.FILE
                elif param_type == 'secret':
                    var_type = VariableType.SECRET
                
                # 创建变量数据（用于缓存的字典格式）
                variable_data = {
                    'name': f"{node_id}.{param_name}",
                    'var_type': var_type.value,
                    'scope': VariableScope.CONVERSATION.value,
                    'value': None,  # 配置阶段的潜在变量，值为None
                    'description': description or f"来自节点 {node_id} 的输出参数 {param_name}",
                    'created_at': datetime.now(UTC).isoformat(),
                    'updated_at': datetime.now(UTC).isoformat(),
                    'step_name': getattr(node, 'name', node_id),  # 节点名称
                    'step_id': node_id  # 节点ID
                }
                
                variables_data.append(variable_data)
            
            logger.debug(f"为节点 {node_id} 创建了 {len(variables_data)} 个输出变量: {[v['name'] for v in variables_data]}")
            return variables_data
            
        except Exception as e:
            logger.error(f"创建节点输出变量失败: {e}")
            return [] 

    @staticmethod
    async def clear_all_predecessor_cache():
        """清空所有前置节点缓存（项目启动时使用）"""
        try:
            if not redis_cache.is_connected():
                logger.warning("Redis未连接，跳过清空缓存")
                return
                
            logger.info("开始清空所有前置节点缓存...")
            
            # 查找所有前置节点缓存相关的key
            cache_patterns = [
                "predecessor_vars:*",  # 缓存的变量数据
                "parsing_status:*",  # 解析状态
                "flow_hash:*"  # Flow哈希值
            ]
            
            total_deleted = 0
            for pattern in cache_patterns:
                try:
                    keys = await redis_cache._redis.keys(pattern)
                    if keys:
                        await redis_cache._redis.delete(*keys)
                        deleted_count = len(keys)
                        total_deleted += deleted_count
                except Exception as e:
                    logger.error(f"清空缓存模式 {pattern} 失败: {e}")
            
            logger.info(f"前置节点缓存清空完成，共删除 {total_deleted} 个缓存key")
            
        except Exception as e:
            logger.error(f"清空所有前置节点缓存失败: {e}") 