import logging
import asyncio
from typing import List, Dict, Any, Optional
from base.search.keyword import search_by_keyword as keyword_search
from base.search.vector import search_by_vector as vector_search
from base.embedding import Embedding
from base.rerank import Rerank

logger = logging.getLogger(__name__)


async def weighted_keyword_and_vector_search(
    conn,
    query: str,
    top_k: int = 5,
    weight_keyword: float = 0.3,
    weight_vector: float = 0.7,
    doc_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    加权关键词和向量混合检索（异步）
    
    :param conn: 数据库连接对象（SQLAlchemy Connection）
    :param query: 查询文本
    :param top_k: 返回数量
    :param weight_keyword: 关键词搜索权重
    :param weight_vector: 向量搜索权重
    :return: 合并后的 chunk 列表
    """
    try:
        # 同时进行关键词和向量搜索，每个获取 2*topk 个结果
        keyword_chunks = []
        vector_chunks = []
        
        # 关键词搜索
        try:
            keyword_chunks = keyword_search(conn, query, 2 * top_k, doc_ids)
        except Exception as e:
            logger.warning(f"[WeightedSearch] 关键词检索失败: {e}")
        
        # 向量搜索（需要 embedding 配置）
        if Embedding.is_configured():
            try:
                query_vector = await Embedding.vectorize_embedding(query)
                if query_vector:
                    vector_chunks = vector_search(conn, query_vector, 2 * top_k, doc_ids)
            except Exception as e:
                logger.warning(f"[WeightedSearch] 向量检索失败: {e}")
        
        # 如果没有结果
        if not keyword_chunks and not vector_chunks:
            return []
        
        # 归一化并合并结果
        merged_chunks = {}
        
        # 处理关键词搜索结果
        if keyword_chunks:
            # 归一化 rank 分数（rank 越小越好，转换为越大越好）
            keyword_scores = [chunk.get('score', 0.0) for chunk in keyword_chunks if chunk.get('score') is not None]
            if keyword_scores:
                min_rank = min(keyword_scores)
                max_rank = max(keyword_scores)
                rank_range = max_rank - min_rank
                
                for chunk in keyword_chunks:
                    chunk_id = chunk['id']
                    rank = chunk.get('score', 0.0)
                    # 转换为越大越好的分数（归一化到 0-1）
                    if rank_range > 0:
                        normalized_score = 1.0 - ((rank - min_rank) / rank_range)
                    else:
                        normalized_score = 1.0
                    weighted_score = normalized_score * weight_keyword
                    
                    if chunk_id not in merged_chunks:
                        merged_chunks[chunk_id] = chunk.copy()
                        merged_chunks[chunk_id]['score'] = weighted_score
                    else:
                        merged_chunks[chunk_id]['score'] += weighted_score
        
        # 处理向量搜索结果
        if vector_chunks:
            # 归一化 distance 分数（distance 越小越好，转换为越大越好）
            vector_scores = [chunk.get('score', 0.0) for chunk in vector_chunks if chunk.get('score') is not None]
            if vector_scores:
                min_distance = min(vector_scores)
                max_distance = max(vector_scores)
                distance_range = max_distance - min_distance
                
                for chunk in vector_chunks:
                    chunk_id = chunk['id']
                    distance = chunk.get('score', 0.0)
                    # 转换为越大越好的分数（归一化到 0-1）
                    if distance_range > 0:
                        normalized_score = 1.0 - ((distance - min_distance) / distance_range)
                    else:
                        normalized_score = 1.0
                    weighted_score = normalized_score * weight_vector
                    
                    if chunk_id not in merged_chunks:
                        merged_chunks[chunk_id] = chunk.copy()
                        merged_chunks[chunk_id]['score'] = weighted_score
                    else:
                        merged_chunks[chunk_id]['score'] += weighted_score
        
        # 转换为列表并按分数排序
        merged_list = list(merged_chunks.values())
        merged_list.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        
        # Rerank
        reranked_chunks = Rerank.rerank_chunks(merged_list, query)
        
        # 取前 top_k 个
        final_chunks = reranked_chunks[:top_k]
        
        return final_chunks
        
    except Exception as e:
        logger.exception(f"[WeightedSearch] 混合检索失败: {e}")
        return []

