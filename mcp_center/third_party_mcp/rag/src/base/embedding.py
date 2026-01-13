import json
import logging
import asyncio
import aiohttp
from typing import Optional, List
from base.config import (
    get_embedding_type,
    get_embedding_api_key,
    get_embedding_endpoint,
    get_embedding_model_name,
    get_embedding_timeout,
    get_embedding_vector_dimension
)

logger = logging.getLogger(__name__)


class Embedding:
    """Embedding 服务类"""
    
    @staticmethod
    def _get_config():
        """获取配置（延迟加载）"""
        return {
            "type": get_embedding_type(),
            "api_key": get_embedding_api_key(),
            "endpoint": get_embedding_endpoint(),
            "model_name": get_embedding_model_name(),
            "timeout": get_embedding_timeout(),
            "vector_dimension": get_embedding_vector_dimension()
        }
    
    @staticmethod
    def is_configured() -> bool:
        config = Embedding._get_config()
        return bool(config["api_key"] and config["endpoint"])
    
    @staticmethod
    async def vectorize_embedding(text: str, session: Optional[aiohttp.ClientSession] = None) -> Optional[List[float]]:
        """
        将文本向量化（异步实现）
        :param text: 文本内容
        :param session: 可选的 aiohttp 会话
        :return: 向量列表
        """
        config = Embedding._get_config()
        vector = None
        should_close_session = False
        
        # 如果没有提供会话，创建一个新的
        if session is None:
            timeout = aiohttp.ClientTimeout(total=config["timeout"])
            connector = aiohttp.TCPConnector(ssl=False)
            session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            should_close_session = True
        
        try:
            if config["type"] == "openai":
                headers = {
                    "Authorization": f"Bearer {config['api_key']}"
                }
                data = {
                    "input": text,
                    "model": config["model_name"],
                    "encoding_format": "float"
                }
                try:
                    async with session.post(
                        url=config["endpoint"],
                        headers=headers,
                        json=data
                    ) as res:
                        if res.status != 200:
                            return None
                        result = await res.json()
                        vector = result['data'][0]['embedding']
                except Exception:
                    return None
            elif config["type"] == "mindie":
                try:
                    data = {
                        "inputs": text,
                    }
                    async with session.post(
                        url=config["endpoint"],
                        json=data
                    ) as res:
                        if res.status != 200:
                            return None
                        text_result = await res.text()
                        vector = json.loads(text_result)[0]
                except Exception:
                    return None
            else:
                return None
            
            # 确保向量长度为配置的维度（不足补0，超过截断）
            if vector:
                vector_dim = config["vector_dimension"]
                while len(vector) < vector_dim:
                    vector.append(0.0)
                return vector[:vector_dim]
            return None
        finally:
            if should_close_session:
                await session.close()
    
    @staticmethod
    async def vectorize_embeddings_batch(texts: List[str], max_concurrent: int = 5) -> List[Optional[List[float]]]:
        """
        批量向量化（并发处理）
        :param texts: 文本列表
        :param max_concurrent: 最大并发数
        :return: 向量列表（与输入文本顺序对应）
        """
        config = Embedding._get_config()
        if not config["api_key"] or not config["endpoint"]:
            return [None] * len(texts)
        
        # 创建共享的 aiohttp 会话（复用连接）
        timeout = aiohttp.ClientTimeout(total=config["timeout"])
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # 使用信号量控制并发数
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def vectorize_with_semaphore(text: str, index: int) -> tuple:
                async with semaphore:
                    vector = await Embedding.vectorize_embedding(text, session=session)
                    return index, vector
            
            tasks = [vectorize_with_semaphore(text, i) for i, text in enumerate(texts)]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            vectors = [None] * len(texts)
            for result in results:
                if isinstance(result, Exception):
                    continue
                index, vector = result
                vectors[index] = vector
            
            return vectors
    

