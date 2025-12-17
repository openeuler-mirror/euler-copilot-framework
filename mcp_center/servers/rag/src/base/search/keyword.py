"""
关键词检索模块 - 使用 SQLAlchemy
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text
import jieba

logger = logging.getLogger(__name__)


def _prepare_fts_query(query: str) -> str:
    """
    准备 FTS5 查询
    :param query: 原始查询文本
    :return: FTS5 查询字符串
    """
    def escape_fts_word(word: str) -> str:
        # 包含以下任意字符时，整体作为短语用双引号包裹，避免触发 FTS5 语法解析
        # 特别是 '%' 在 FTS5 MATCH 语法中会导致 "syntax error near '%'"
        special_chars = [
            '"', "'", '(', ')', '*', ':', '?', '+', '-', '|', '&',
            '{', '}', '[', ']', '^', '$', '\\', '/', '!', '~', ';',
            ',', '.', ' ', '%'
        ]
        if any(char in word for char in special_chars):
            escaped_word = word.replace('"', '""')
            return f'"{escaped_word}"'
        return word
    
    try:
        words = jieba.cut(query)
        words = [word.strip() for word in words if word.strip()]
        if not words:
            return escape_fts_word(query)
        
        escaped_words = [escape_fts_word(word) for word in words]
        fts_query = ' OR '.join(escaped_words)
        return fts_query
    except Exception:
        return escape_fts_word(query)


def search_by_keyword(conn, query: str, top_k: int = 5, doc_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    关键词检索（FTS5，使用 jieba 对中文进行分词）
    :param conn: 数据库连接对象（SQLAlchemy Connection）
    :param query: 查询文本
    :param top_k: 返回数量
    :param doc_ids: 可选的文档ID列表，用于过滤
    :return: chunk 列表
    """
    try:
        fts_query = _prepare_fts_query(query)
        
        params = {"fts_query": fts_query, "top_k": top_k}
        where_clause = "WHERE chunks_fts MATCH :fts_query"
        
        if doc_ids:
            placeholders = ','.join([f':doc_id_{i}' for i in range(len(doc_ids))])
            for i, doc_id in enumerate(doc_ids):
                params[f'doc_id_{i}'] = doc_id
            where_clause += f" AND c.doc_id IN ({placeholders})"
        
        sql = f"""
            SELECT c.id, c.doc_id, c.content, c.tokens, c.chunk_index,
                   d.name as doc_name,
                   chunks_fts.rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.id
            JOIN documents d ON d.id = c.doc_id
            {where_clause}
            ORDER BY chunks_fts.rank
            LIMIT :top_k
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
                'score': row.rank if row.rank is not None else 0.0
            })
        return results
    except Exception as e:
        logger.exception(f"[KeywordSearch] 关键词检索失败: {e}")
        return []
