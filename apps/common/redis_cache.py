# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Redis缓存模块 - 用于前置节点变量预解析缓存"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

import redis.asyncio as redis
from apps.common.singleton import SingletonMeta

logger = logging.getLogger(__name__)


class RedisCache(metaclass=SingletonMeta):
    """Redis缓存管理器"""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        
    async def init(self, redis_config=None, redis_url: str = None):
        """初始化Redis连接
        
        Args:
            redis_config: Redis配置对象（优先级更高）
            redis_url: Redis连接URL（降级选项）
        """
        try:
            if redis_config:
                # 使用配置对象构建连接，添加连接池和超时参数
                self._redis = redis.Redis(
                    host=redis_config.host,
                    port=redis_config.port,
                    password=redis_config.password if redis_config.password else None,
                    db=redis_config.database,
                    decode_responses=redis_config.decode_responses,
                    # 连接池配置
                    max_connections=redis_config.max_connections,
                    # 超时配置
                    socket_timeout=redis_config.socket_timeout,
                    socket_connect_timeout=redis_config.socket_connect_timeout,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    # 连接重试
                    retry_on_timeout=True,
                    retry_on_error=[ConnectionError, TimeoutError],
                    health_check_interval=redis_config.health_check_interval
                )
                logger.info(f"使用配置连接Redis: {redis_config.host}:{redis_config.port}, 数据库: {redis_config.database}")
            elif redis_url:
                # 降级使用URL连接
                self._redis = redis.from_url(
                    redis_url, 
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                    max_connections=10
                )
                logger.info(f"使用URL连接Redis: {redis_url}")
            else:
                raise ValueError("必须提供redis_config或redis_url参数")
            
            # 测试连接
            logger.info("正在测试Redis连接...")
            ping_result = await self._redis.ping()
            logger.info(f"Redis ping结果: {ping_result}")
            
            # 测试基本操作
            test_key = "__redis_test__"
            await self._redis.set(test_key, "test", ex=10)
            test_value = await self._redis.get(test_key)
            await self._redis.delete(test_key)
            logger.info(f"Redis读写测试成功: {test_value}")
            
            self._connected = True
            logger.info("Redis连接初始化成功")
        except ConnectionError as e:
            logger.error(f"Redis连接错误: {e}")
            self._connected = False
        except TimeoutError as e:
            logger.error(f"Redis连接超时: {e}")
            self._connected = False
        except Exception as e:
            logger.error(f"Redis连接初始化失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            self._connected = False
    
    def is_connected(self) -> bool:
        """检查Redis连接状态"""
        return self._connected and self._redis is not None
    
    async def close(self):
        """关闭Redis连接"""
        if self._redis:
            await self._redis.close()
            self._connected = False


class PredecessorVariableCache:
    """前置节点变量预解析缓存管理器"""
    
    def __init__(self, redis_cache: RedisCache):
        self.redis = redis_cache
        self.CACHE_PREFIX = "predecessor_vars"
        self.PARSING_STATUS_PREFIX = "parsing_status"
        self.CACHE_TTL = 3600 * 24  # 缓存24小时
        
    def _get_cache_key(self, flow_id: str, step_id: str) -> str:
        """生成缓存key"""
        return f"{self.CACHE_PREFIX}:{flow_id}:{step_id}"
    
    def _get_status_key(self, flow_id: str, step_id: str) -> str:
        """生成解析状态key"""
        return f"{self.PARSING_STATUS_PREFIX}:{flow_id}:{step_id}"
    
    def _get_flow_hash_key(self, flow_id: str) -> str:
        """生成Flow哈希key，用于存储Flow的拓扑结构哈希值"""
        return f"flow_hash:{flow_id}"
    
    async def get_cached_variables(self, flow_id: str, step_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的前置节点变量"""
        if not self.redis.is_connected():
            return None
            
        try:
            cache_key = self._get_cache_key(flow_id, step_id)
            cached_data = await self.redis._redis.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                logger.info(f"从缓存获取前置节点变量: {flow_id}:{step_id}, 数量: {len(data.get('variables', []))}")
                return data.get('variables', [])
                
        except Exception as e:
            logger.error(f"获取缓存的前置节点变量失败: {e}")
            
        return None
    
    async def set_cached_variables(self, flow_id: str, step_id: str, variables: List[Dict[str, Any]], flow_hash: str):
        """设置缓存的前置节点变量"""
        if not self.redis.is_connected():
            return False
            
        try:
            cache_key = self._get_cache_key(flow_id, step_id)
            cache_data = {
                'variables': variables,
                'flow_hash': flow_hash,
                'cached_at': datetime.now(UTC).isoformat(),
                'step_count': len(variables)
            }
            
            await self.redis._redis.setex(
                cache_key, 
                self.CACHE_TTL, 
                json.dumps(cache_data, default=str)
            )
            
            logger.info(f"缓存前置节点变量成功: {flow_id}:{step_id}, 数量: {len(variables)}")
            return True
            
        except Exception as e:
            logger.error(f"缓存前置节点变量失败: {e}")
            return False
    
    async def is_parsing_in_progress(self, flow_id: str, step_id: str) -> bool:
        """检查是否正在解析中"""
        if not self.redis.is_connected():
            return False
            
        try:
            status_key = self._get_status_key(flow_id, step_id)
            status = await self.redis._redis.get(status_key)
            return status == "parsing"
        except Exception as e:
            logger.error(f"检查解析状态失败: {e}")
            return False
    
    async def set_parsing_status(self, flow_id: str, step_id: str, status: str, ttl: int = 300):
        """设置解析状态 (parsing, completed, failed)"""
        if not self.redis.is_connected():
            return False
            
        try:
            status_key = self._get_status_key(flow_id, step_id)
            await self.redis._redis.setex(status_key, ttl, status)
            return True
        except Exception as e:
            logger.error(f"设置解析状态失败: {e}")
            return False
    
    async def wait_for_parsing_completion(self, flow_id: str, step_id: str, max_wait_time: int = 30) -> bool:
        """等待解析完成"""
        if not self.redis.is_connected():
            return False
            
        start_time = datetime.now(UTC)
        
        while (datetime.now(UTC) - start_time).total_seconds() < max_wait_time:
            if not await self.is_parsing_in_progress(flow_id, step_id):
                # 检查是否有缓存结果
                cached_vars = await self.get_cached_variables(flow_id, step_id)
                return cached_vars is not None
            
            await asyncio.sleep(0.5)  # 等待500ms后重试
            
        logger.warning(f"等待解析完成超时: {flow_id}:{step_id}")
        return False
    
    async def invalidate_flow_cache(self, flow_id: str):
        """使某个Flow的所有缓存失效"""
        if not self.redis.is_connected():
            return
            
        try:
            # 查找所有相关的缓存key
            pattern = f"{self.CACHE_PREFIX}:{flow_id}:*"
            keys = await self.redis._redis.keys(pattern)
            
            # 同时删除解析状态key
            status_pattern = f"{self.PARSING_STATUS_PREFIX}:{flow_id}:*"
            status_keys = await self.redis._redis.keys(status_pattern)
            
            all_keys = keys + status_keys
            
            if all_keys:
                await self.redis._redis.delete(*all_keys)
                logger.info(f"清除Flow缓存: {flow_id}, 删除key数量: {len(all_keys)}")
                
        except Exception as e:
            logger.error(f"清除Flow缓存失败: {e}")
    
    async def get_flow_hash(self, flow_id: str) -> Optional[str]:
        """获取Flow的拓扑结构哈希值"""
        if not self.redis.is_connected():
            return None
            
        try:
            hash_key = self._get_flow_hash_key(flow_id)
            return await self.redis._redis.get(hash_key)
        except Exception as e:
            logger.error(f"获取Flow哈希失败: {e}")
            return None
    
    async def set_flow_hash(self, flow_id: str, flow_hash: str):
        """设置Flow的拓扑结构哈希值"""
        if not self.redis.is_connected():
            return False
            
        try:
            # 检查事件循环是否仍然活跃
            import asyncio
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                logger.warning(f"事件循环已关闭，跳过设置Flow哈希: {flow_id}")
                return False
                
            hash_key = self._get_flow_hash_key(flow_id)
            await self.redis._redis.setex(hash_key, self.CACHE_TTL, flow_hash)
            return True
        except Exception as e:
            logger.error(f"设置Flow哈希失败: {e}")
            return False


# 全局实例
redis_cache = RedisCache()
predecessor_cache = PredecessorVariableCache(redis_cache) 