"""
向量检索模块 - 使用 SQLAlchemy
"""
import logging
import struct
from typing import List, Dict, Any, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


def search_by_vector(conn, query_vector: List[float], top_k: int = 5, doc_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    向量检索
    :param conn: 数据库连接对象（SQLAlchemy Connection）
    :param query_vector: 查询向量
    :param top_k: 返回数量
    :param doc_ids: 可选的文档ID列表，用于过滤
    :return: chunk 列表
    """
    try:
        # 检查 vec_index 表是否存在
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='vec_index'
        """))
        if not result.fetchone():
            return []
        
        query_vector_bytes = struct.pack(f'{len(query_vector)}f', *query_vector)
        
        params = {"query_vector": query_vector_bytes, "top_k": top_k}
        where_clause = "WHERE v.embedding MATCH :query_vector AND k = :top_k"
        
        if doc_ids:
            placeholders = ','.join([f':doc_id_{i}' for i in range(len(doc_ids))])
            for i, doc_id in enumerate(doc_ids):
                params[f'doc_id_{i}'] = doc_id
            where_clause += f" AND c.doc_id IN ({placeholders})"
        
        sql = f"""
            SELECT c.id, c.doc_id, c.content, c.tokens, c.chunk_index,
                   d.name as doc_name,
                   distance
            FROM vec_index v
            JOIN chunks c ON c.rowid = v.rowid
            JOIN documents d ON d.id = c.doc_id
            {where_clause}
            ORDER BY distance
        """
        result = conn.execute(text(sql), params)
        
        results = []
        for row in result:
            results.append({
                'id': row.id,
                'doc_id': row.doc_id,
                'content': row.content,
                'tokens': row.tokens,
                'chunk_index': row.chunk_index,
                'doc_name': row.doc_name,
                'score': row.distance
            })
        return results
    except Exception as e:
        logger.exception(f"[VectorSearch] 向量检索失败: {e}")
        return []
