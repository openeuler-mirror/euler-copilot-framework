"""
文档操作模块 - 使用 SQLAlchemy ORM
"""
import os
import struct
import uuid
import asyncio
from typing import List, Optional, Tuple
from datetime import datetime
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from base.models import Document, Chunk
from base.embedding import Embedding
from base.parser.parser import Parser
from base.token_tool import TokenTool
import jieba

logger = logging.getLogger(__name__)


class DocumentManager:
    """文档操作管理器"""
    
    def __init__(self, session: Session):
        """
        初始化文档管理器
        :param session: 数据库会话
        """
        self.session = session
    
    def add_document(self, doc_id: str, kb_id: str, name: str, file_path: str, 
                    file_type: str, content: Optional[str] = None, chunk_size: Optional[int] = None) -> bool:
        """添加文档"""
        try:
            document = Document(
                id=doc_id,
                kb_id=kb_id,
                name=name,
                file_path=file_path,
                file_type=file_type,
                content=content,
                chunk_size=chunk_size,
                updated_at=datetime.now()
            )
            self.session.add(document)
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.exception(f"[DocumentManager] 添加文档失败: {e}")
            self.session.rollback()
            return False
    
    def delete_document(self, kb_id: str, doc_name: str) -> bool:
        """删除文档（级联删除相关chunks）"""
        try:
            doc = self.session.query(Document).filter_by(kb_id=kb_id, name=doc_name).first()
            if doc:
                self.session.delete(doc)
                self.session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            logger.exception(f"[DocumentManager] 删除文档失败: {e}")
            self.session.rollback()
            return False
    
    def get_document(self, kb_id: str, doc_name: str) -> Optional[Document]:
        """获取文档"""
        return self.session.query(Document).filter_by(kb_id=kb_id, name=doc_name).first()
    
    def list_documents_by_kb(self, kb_id: str) -> List[Document]:
        """列出知识库下的所有文档"""
        return self.session.query(Document).filter_by(kb_id=kb_id).order_by(Document.created_at.desc()).all()
    
    def add_chunk(self, chunk_id: str, doc_id: str, content: str, tokens: int, chunk_index: int, 
                  embedding: Optional[List[float]] = None) -> bool:
        """添加 chunk（可包含向量）"""
        try:
            embedding_bytes = None
            if embedding:
                embedding_bytes = struct.pack(f'{len(embedding)}f', *embedding)
            
            chunk = Chunk(
                id=chunk_id,
                doc_id=doc_id,
                content=content,
                tokens=tokens,
                chunk_index=chunk_index,
                embedding=embedding_bytes
            )
            self.session.add(chunk)
            self.session.flush()
            
            # 添加 FTS5 索引（需要使用原生 SQL）
            fts_content = self._prepare_fts_content(content)
            self.session.execute(text("""
                INSERT INTO chunks_fts (id, content)
                VALUES (:chunk_id, :content)
            """), {"chunk_id": chunk_id, "content": fts_content})
            
            # 检查并更新 vec_index（需要使用原生 SQL）
            if embedding_bytes:
                conn = self.session.connection()
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='vec_index'
                """))
                if result.fetchone():
                    result = conn.execute(text("""
                        SELECT rowid FROM chunks WHERE id = :chunk_id
                    """), {"chunk_id": chunk_id})
                    row = result.fetchone()
                    if row:
                        vec_rowid = row[0]
                        # 先删除可能存在的旧记录，避免 UNIQUE constraint 冲突
                        conn.execute(text("""
                            DELETE FROM vec_index WHERE rowid = :rowid
                        """), {"rowid": vec_rowid})
                        # 然后插入新记录
                        conn.execute(text("""
                            INSERT INTO vec_index(rowid, embedding)
                            VALUES (:rowid, :embedding)
                        """), {"rowid": vec_rowid, "embedding": embedding_bytes})
            
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.exception(f"[DocumentManager] 添加chunk失败: {e}")
            self.session.rollback()
            return False
    
    def _prepare_fts_content(self, content: str) -> str:
        """
        准备 FTS5 内容（对中文进行 jieba 分词）
        :param content: 原始内容
        :return: 分词后的内容（用空格连接）
        """
        try:
            words = jieba.cut(content)
            words = [word.strip() for word in words if word.strip()]
            return ' '.join(words)
        except Exception:
            return content
    
    def update_chunk_embedding(self, chunk_id: str, embedding: List[float]) -> bool:
        """更新 chunk 的向量"""
        try:
            embedding_bytes = struct.pack(f'{len(embedding)}f', *embedding)
            
            chunk = self.session.query(Chunk).filter_by(id=chunk_id).first()
            if not chunk:
                return False
            
            chunk.embedding = embedding_bytes
            self.session.flush()
            
            # 检查并更新 vec_index（需要使用原生 SQL）
            conn = self.session.connection()
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='vec_index'
            """))
            if result.fetchone():
                result = conn.execute(text("""
                    SELECT rowid FROM chunks WHERE id = :chunk_id
                """), {"chunk_id": chunk_id})
                row = result.fetchone()
                if row:
                    vec_rowid = row[0]
                    # 先删除可能存在的旧记录，避免 UNIQUE constraint 冲突
                    conn.execute(text("""
                        DELETE FROM vec_index WHERE rowid = :rowid
                    """), {"rowid": vec_rowid})
                    # 然后插入新记录
                    conn.execute(text("""
                        INSERT INTO vec_index(rowid, embedding)
                        VALUES (:rowid, :embedding)
                    """), {"rowid": vec_rowid, "embedding": embedding_bytes})
            
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.exception(f"[DocumentManager] 更新chunk向量失败: {e}")
            self.session.rollback()
            return False
    
    def delete_document_chunks(self, doc_id: str) -> None:
        """删除文档的所有chunks"""
        chunks = self.session.query(Chunk).filter_by(doc_id=doc_id).all()
        conn = self.session.connection()
        for chunk in chunks:
            # 删除FTS5索引
            conn.execute(text("""
                DELETE FROM chunks_fts WHERE id = :chunk_id
            """), {"chunk_id": chunk.id})
            # 删除向量索引（如果chunk有向量）
            if chunk.embedding:
                result = conn.execute(text("""
                    SELECT rowid FROM chunks WHERE id = :chunk_id
                """), {"chunk_id": chunk.id})
                row = result.fetchone()
                if row:
                    conn.execute(text("""
                        DELETE FROM vec_index WHERE rowid = :rowid
                    """), {"rowid": row[0]})
            # 删除chunk
            self.session.delete(chunk)
        self.session.commit()
    
    def update_document_content(self, doc_id: str, content: str, chunk_size: int) -> None:
        """更新文档的content和chunk_size"""
        doc = self.session.query(Document).filter_by(id=doc_id).first()
        if doc:
            doc.chunk_size = chunk_size
            doc.content = content
            doc.updated_at = datetime.now()
            self.session.commit()


def _generate_unique_name(base_name: str, check_exists_func) -> str:
    """
    生成唯一名称，如果已存在则添加时间戳
    
    :param base_name: 基础名称
    :param check_exists_func: 检查是否存在的函数，接受名称参数，返回是否存在
    :return: 唯一名称
    """
    if not check_exists_func(base_name):
        return base_name
    
    # 如果已存在，添加时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 分离文件名和扩展名
    if '.' in base_name:
        name_part, ext_part = base_name.rsplit('.', 1)
        new_name = f"{name_part}_{timestamp}.{ext_part}"
    else:
        new_name = f"{base_name}_{timestamp}"
    
    # 如果新名称仍然存在，继续添加后缀
    counter = 1
    final_name = new_name
    while check_exists_func(final_name):
        if '.' in base_name:
            name_part, ext_part = base_name.rsplit('.', 1)
            final_name = f"{name_part}_{timestamp}_{counter}.{ext_part}"
        else:
            final_name = f"{base_name}_{timestamp}_{counter}"
        counter += 1
    
    return final_name


async def import_document(session: Session, kb_id: str, file_path: str, 
                         chunk_size: int) -> Tuple[bool, str, Optional[dict]]:
    """
    导入文档（异步）
    
    :param session: 数据库会话
    :param kb_id: 知识库ID
    :param file_path: 文件路径
    :param chunk_size: chunk大小
    :return: (success, message, data)
    """
    try:
        doc_name = os.path.basename(file_path)
        content = Parser.parse(file_path)
        if not content:
            return False, "文档解析失败", None
        
        chunks = TokenTool.split_content_to_chunks(content, chunk_size)
        if not chunks:
            return False, "文档内容为空", None
        
        manager = DocumentManager(session)
        
        # 检查文档是否已存在，如果存在则生成唯一名称
        def check_doc_exists(name: str) -> bool:
            return manager.get_document(kb_id, name) is not None
        
        unique_doc_name = _generate_unique_name(doc_name, check_doc_exists)
        
        doc_id = str(uuid.uuid4())
        file_type = file_path.lower().split('.')[-1]
        
        if not manager.add_document(doc_id, kb_id, unique_doc_name, file_path, file_type, content, chunk_size):
            return False, "添加文档失败", None
        
        chunk_ids = []
        chunk_data = []
        
        # 先收集所有chunk数据
        for idx, chunk_content in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            tokens = TokenTool.get_tokens(chunk_content)
            chunk_data.append((chunk_id, chunk_content, tokens, idx))
        
        # 批量生成向量（异步）
        embeddings_list = [None] * len(chunk_data)
        if Embedding.is_configured() and chunk_data:
            try:
                chunk_contents = [content for _, content, _, _ in chunk_data]
                embeddings_list = await Embedding.vectorize_embeddings_batch(chunk_contents, max_concurrent=5)
            except Exception as e:
                logger.warning(f"批量生成向量失败: {e}")
        
        # 添加chunks（包含向量）
        for (chunk_id, chunk_content, tokens, idx), embedding in zip(chunk_data, embeddings_list):
            if manager.add_chunk(chunk_id, doc_id, chunk_content, tokens, idx, embedding):
                chunk_ids.append(chunk_id)
        
        return True, f"成功导入文档，共 {len(chunk_ids)} 个 chunks", {
            "doc_id": doc_id,
            "doc_name": unique_doc_name,
            "original_name": doc_name if unique_doc_name != doc_name else None,
            "chunk_count": len(chunk_ids),
            "file_path": file_path
        }
    except Exception as e:
        logger.exception(f"[import_document] 导入文档失败: {e}")
        return False, "导入文档失败", None


async def update_document(session: Session, kb_id: str, doc_name: str, chunk_size: int) -> Tuple[bool, str, Optional[dict]]:
    """
    更新文档的chunk_size并重新解析（异步）
    
    :param session: 数据库会话
    :param kb_id: 知识库ID
    :param doc_name: 文档名称
    :param chunk_size: 新的chunk大小
    :return: (success, message, data)
    """
    try:
        manager = DocumentManager(session)
        doc = manager.get_document(kb_id, doc_name)
        if not doc:
            return False, f"文档 '{doc_name}' 不存在", None
        
        # 删除旧文档的所有chunks
        manager.delete_document_chunks(doc.id)
        
        # 重新解析文档
        if not doc.file_path or not os.path.exists(doc.file_path):
            return False, "文档文件不存在", None
        
        content = Parser.parse(doc.file_path)
        if not content:
            return False, "文档解析失败", None
        
        chunks = TokenTool.split_content_to_chunks(content, chunk_size)
        if not chunks:
            return False, "文档内容为空", None
        
        # 收集所有chunk数据
        chunk_ids = []
        chunk_data = []
        
        for idx, chunk_content in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            tokens = TokenTool.get_tokens(chunk_content)
            chunk_data.append((chunk_id, chunk_content, tokens, idx))
        
        # 批量生成向量（异步）
        embeddings_list = [None] * len(chunk_data)
        if Embedding.is_configured() and chunk_data:
            try:
                chunk_contents = [content for _, content, _, _ in chunk_data]
                embeddings_list = await Embedding.vectorize_embeddings_batch(chunk_contents, max_concurrent=5)
            except Exception as e:
                logger.warning(f"批量生成向量失败: {e}")
        
        # 添加chunks（包含向量）
        for (chunk_id, chunk_content, tokens, idx), embedding in zip(chunk_data, embeddings_list):
            if manager.add_chunk(chunk_id, doc.id, chunk_content, tokens, idx, embedding):
                chunk_ids.append(chunk_id)
        
        # 更新文档的chunk_size和content
        manager.update_document_content(doc.id, content, chunk_size)
        
        return True, f"成功修改文档，共 {len(chunk_ids)} 个 chunks", {
            "doc_id": doc.id,
            "doc_name": doc_name,
            "chunk_count": len(chunk_ids),
            "chunk_size": chunk_size
        }
    except Exception as e:
        logger.exception(f"[update_document] 修改文档失败: {e}")
        return False, "修改文档失败", None

