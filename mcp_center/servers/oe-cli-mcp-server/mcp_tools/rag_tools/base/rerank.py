import jieba
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class Rerank:
    """Rerank 类（使用 Jaccard 相似度）"""
    
    stopwords = set(['的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'])
    
    @staticmethod
    def split_words(content: str) -> List[str]:
        try:
            return list(jieba.cut(str(content)))
        except Exception:
            return []
    
    @staticmethod
    def cal_jaccard(str1: str, str2: str) -> float:
        try:
            if len(str1) == 0 and len(str2) == 0:
                return 100.0
            
            words1 = Rerank.split_words(str1)
            words2 = Rerank.split_words(str2)
            
            new_words1 = [word for word in words1 if word not in Rerank.stopwords and word.strip()]
            new_words2 = [word for word in words2 if word not in Rerank.stopwords and word.strip()]
            
            if len(new_words1) == 0 or len(new_words2) == 0:
                return 0.0
            
            set1 = set(new_words1)
            set2 = set(new_words2)
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            if union == 0:
                return 0.0
            
            score = intersection / union * 100.0
            return score
        except Exception:
            return 0.0
    
    @staticmethod
    def rerank_chunks(chunks: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        try:
            score_chunks = []
            for chunk in chunks:
                content = chunk.get('content', '')
                score = Rerank.cal_jaccard(content, query)
                chunk['jaccard_score'] = score
                score_chunks.append((score, chunk))
            
            # 按 Jaccard 分数降序排序
            score_chunks.sort(key=lambda x: x[0], reverse=True)
            sorted_chunks = [chunk for _, chunk in score_chunks]
            
            return sorted_chunks
        except Exception:
            return chunks

