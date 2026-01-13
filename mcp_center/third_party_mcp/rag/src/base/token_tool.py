import tiktoken
import logging
import re
import uuid
from typing import List
from base.config import get_token_model, get_max_tokens

logger = logging.getLogger(__name__)


class TokenTool:
    """Token 工具类"""
    
    _encoding_cache = {}
    
    @staticmethod
    def _get_encoding():
        """
        获取编码器（带缓存）
        :return: tiktoken 编码器
        """
        model = get_token_model()
        if model not in TokenTool._encoding_cache:
            try:
                TokenTool._encoding_cache[model] = tiktoken.encoding_for_model(model)
            except Exception:
                TokenTool._encoding_cache[model] = tiktoken.get_encoding("cl100k_base")
        return TokenTool._encoding_cache[model]
    
    @staticmethod
    def get_tokens(content: str) -> int:
        """
        获取文本的 token 数量
        :param content: 文本内容
        :return: token 数量
        """
        try:
            enc = TokenTool._get_encoding()
            return len(enc.encode(str(content)))
        except Exception:
            return 0
    
    @staticmethod
    def get_k_tokens_words_from_content(content: str, k: int = 1024) -> str:
        """
        从内容中获取 k 个 token 的文本
        :param content: 文本内容
        :param k: token 数量
        :return: 截取后的文本
        """
        try:
            if TokenTool.get_tokens(content) <= k:
                return content
            
            # 使用二分查找找到合适的截取位置
            l = 0
            r = len(content)
            while l + 1 < r:
                mid = (l + r) // 2
                if TokenTool.get_tokens(content[:mid]) <= k:
                    l = mid
                else:
                    r = mid
            return content[:l]
        except Exception:
            return ""
    
    @staticmethod
    def content_to_sentences(content: str) -> List[str]:
        """
        将内容分割为句子
        :param content: 文本内容
        :return: 句子列表
        """
        protected_phrases = [
            'e.g.', 'i.e.', 'U.S.', 'U.K.', 'A.M.', 'P.M.', 'a.m.', 'p.m.',
            'Inc.', 'Ltd.', 'No.', 'vs.', 'approx.', 'Dr.', 'Mr.', 'Ms.', 'Prof.',
        ]
        
        placeholder_map = {}
        for phrase in protected_phrases:
            placeholder = f"__PROTECTED_{uuid.uuid4().hex}__"
            placeholder_map[placeholder] = phrase
            content = content.replace(phrase, placeholder)
        
        # 分句正则模式
        chinese_punct = r'[。！？!?；;]'
        right_quotes = r'["'""'】】》〕〉）\\]]'
        pattern = re.compile(
            rf'(?<={chinese_punct}{right_quotes})'   
            rf'|(?<={chinese_punct})(?=[^{right_quotes}])'  
            r'|(?<=[\.\?!;])(?=\s|$)'                   
        )
        
        # 分割并还原
        sentences = []
        for segment in pattern.split(content):
            segment = segment.strip()
            if not segment:
                continue
            for placeholder, original in placeholder_map.items():
                segment = segment.replace(placeholder, original)
            sentences.append(segment)
        
        return sentences
    
    @staticmethod
    def split_content_to_chunks(content: str, chunk_size: int = 1024) -> List[str]:
        """
        将内容切分为 chunks
        :param content: 文本内容
        :param chunk_size: chunk 大小（token 数）
        :return: chunk 列表
        """
        try:
            sentences = TokenTool.content_to_sentences(content)
            chunks = []
            current_chunk = ""
            current_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = TokenTool.get_tokens(sentence)
                
                # 如果单个句子超过 chunk_size，需要进一步切分
                if sentence_tokens > chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""
                        current_tokens = 0
                    
                    # 切分长句子
                    sub_content = sentence
                    while TokenTool.get_tokens(sub_content) > chunk_size:
                        sub_chunk = TokenTool.get_k_tokens_words_from_content(sub_content, chunk_size)
                        chunks.append(sub_chunk)
                        sub_content = sub_content[len(sub_chunk):]
                    
                    if sub_content:
                        current_chunk = sub_content
                        current_tokens = TokenTool.get_tokens(sub_content)
                else:
                    if current_tokens + sentence_tokens > chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = sentence
                        current_tokens = sentence_tokens
                    else:
                        current_chunk += sentence
                        current_tokens += sentence_tokens
            
            if current_chunk:
                chunks.append(current_chunk)
            
            return chunks
        except Exception:
            return []

