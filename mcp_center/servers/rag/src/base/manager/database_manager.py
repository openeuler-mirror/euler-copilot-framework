"""
数据库操作类 - 使用 SQLAlchemy ORM
"""
import os
import struct
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from base.models import Base, KnowledgeBase, Document, Chunk
from base.config import get_embedding_vector_dimension
from base.manager.document_manager import DocumentManager
import sqlite_vec

logger = logging.getLogger(__name__)


class Database:
    """SQLite 数据库操作类 - 使用 SQLAlchemy ORM"""
    
    def __init__(self, db_path: str = "knowledge_base.db"):
        """
        初始化数据库连接
        :param db_path: 数据库文件路径
        """
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self.db_path = os.path.abspath(db_path)
        self.engine = create_engine(
            f'sqlite:///{self.db_path}',
            echo=False,
            connect_args={'check_same_thread': False}
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            # 创建所有表
            Base.metadata.create_all(self.engine)
            
            # 加载 sqlite-vec 扩展并创建 FTS5 和 vec_index 表
            with self.engine.begin() as conn:
                # 创建 FTS5 虚拟表（需要使用原生 SQL）
                conn.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                        id UNINDEXED,
                        content,
                        content_rowid=id
                    )
                """))
                
                # 加载 sqlite-vec 扩展
                try:
                    raw_conn = conn.connection.dbapi_connection
                    raw_conn.enable_load_extension(True)
                    sqlite_vec.load(raw_conn)
                    raw_conn.enable_load_extension(False)
                except Exception as e:
                    logger.warning(f"加载 sqlite-vec 扩展失败: {e}")
                
                # 创建 vec_index 虚拟表
                try:
                    vector_dim = get_embedding_vector_dimension()
                    conn.execute(text(f"""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_index USING vec0(
                            embedding float[{vector_dim}]
                        )
                    """))
                except Exception as e:
                    logger.warning(f"创建 vec_index 表失败: {e}")
        except Exception as e:
            logger.exception(f"[Database] 初始化数据库失败: {e}")
            raise e
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    def get_connection(self):
        """
        获取原始数据库连接（用于特殊操作，如 FTS5 和 vec_index）
        注意：此方法保留以兼容现有代码，但推荐使用 get_session()
        返回一个上下文管理器，使用后会自动关闭
        """
        return self.engine.connect()
    
    def add_knowledge_base(self, kb_id: str, name: str, chunk_size: int, 
                          embedding_model: Optional[str] = None,
                          embedding_endpoint: Optional[str] = None,
                          embedding_api_key: Optional[str] = None) -> bool:
        """添加知识库"""
        session = self.get_session()
        try:
            kb = KnowledgeBase(
                id=kb_id,
                name=name,
                chunk_size=chunk_size,
                embedding_model=embedding_model,
                embedding_endpoint=embedding_endpoint,
                embedding_api_key=embedding_api_key
            )
            session.add(kb)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.exception(f"[Database] 添加知识库失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_knowledge_base(self, kb_name: str) -> Optional[KnowledgeBase]:
        """获取知识库"""
        session = self.get_session()
        try:
            return session.query(KnowledgeBase).filter_by(name=kb_name).first()
        finally:
            session.close()
    
    def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库（级联删除相关文档和chunks）"""
        session = self.get_session()
        try:
            kb = session.query(KnowledgeBase).filter_by(id=kb_id).first()
            if kb:
                session.delete(kb)
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            logger.exception(f"[Database] 删除知识库失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def list_knowledge_bases(self) -> List[KnowledgeBase]:
        """列出所有知识库"""
        session = self.get_session()
        try:
            return session.query(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()).all()
        finally:
            session.close()
    
    def import_database(self, source_db_path: str) -> tuple[int, int]:
        """
        导入数据库，将其中的内容合并到当前数据库
        
        :param source_db_path: 源数据库文件路径
        :return: (imported_kb_count, imported_doc_count)
        """
        source_db = Database(source_db_path)
        source_session = source_db.get_session()
        
        try:
            # 读取源数据库的知识库
            source_kbs = source_session.query(KnowledgeBase).all()
            if not source_kbs:
                return 0, 0
            
            # 读取源数据库的文档
            source_docs = source_session.query(Document).all()
            
            # 合并到当前数据库
            target_session = self.get_session()
            
            try:
                imported_kb_count = 0
                imported_doc_count = 0
                
                for source_kb in source_kbs:
                    # 检查知识库是否已存在，如果存在则生成唯一名称
                    kb_name = source_kb.name
                    existing_kb = self.get_knowledge_base(kb_name)
                    if existing_kb:
                        # 生成唯一名称
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        counter = 1
                        unique_kb_name = f"{kb_name}_{timestamp}"
                        while self.get_knowledge_base(unique_kb_name):
                            unique_kb_name = f"{kb_name}_{timestamp}_{counter}"
                            counter += 1
                        kb_name = unique_kb_name
                    
                    # 导入知识库
                    new_kb_id = str(uuid.uuid4())
                    if self.add_knowledge_base(new_kb_id, kb_name, source_kb.chunk_size,
                                              source_kb.embedding_model, source_kb.embedding_endpoint,
                                              source_kb.embedding_api_key):
                        imported_kb_count += 1
                        
                        # 导入该知识库下的文档
                        kb_docs = [doc for doc in source_docs if doc.kb_id == source_kb.id]
                        manager = DocumentManager(target_session)
                        
                        for source_doc in kb_docs:
                            # 检查文档是否已存在，如果存在则生成唯一名称
                            doc_name = source_doc.name
                            existing_doc = manager.get_document(new_kb_id, doc_name)
                            if existing_doc:
                                # 生成唯一名称
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                
                                # 分离文件名和扩展名
                                if '.' in doc_name:
                                    name_part, ext_part = doc_name.rsplit('.', 1)
                                    unique_doc_name = f"{name_part}_{timestamp}.{ext_part}"
                                else:
                                    unique_doc_name = f"{doc_name}_{timestamp}"
                                
                                # 如果新名称仍然存在，继续添加后缀
                                counter = 1
                                final_doc_name = unique_doc_name
                                while manager.get_document(new_kb_id, final_doc_name):
                                    if '.' in doc_name:
                                        name_part, ext_part = doc_name.rsplit('.', 1)
                                        final_doc_name = f"{name_part}_{timestamp}_{counter}.{ext_part}"
                                    else:
                                        final_doc_name = f"{doc_name}_{timestamp}_{counter}"
                                    counter += 1
                                doc_name = final_doc_name
                            
                            # 导入文档
                            new_doc_id = str(uuid.uuid4())
                            if manager.add_document(new_doc_id, new_kb_id, doc_name,
                                                  source_doc.file_path, source_doc.file_type,
                                                  source_doc.content, source_doc.chunk_size):
                                imported_doc_count += 1
                                
                                # 导入chunks（包含向量）
                                source_chunks = source_session.query(Chunk).filter_by(doc_id=source_doc.id).all()
                                for source_chunk in source_chunks:
                                    new_chunk_id = str(uuid.uuid4())
                                    # 提取向量（如果存在）
                                    embedding = None
                                    if source_chunk.embedding:
                                        embedding_bytes = source_chunk.embedding
                                        if len(embedding_bytes) > 0 and len(embedding_bytes) % 4 == 0:
                                            embedding = list(struct.unpack(f'{len(embedding_bytes)//4}f', embedding_bytes))
                                    
                                    manager.add_chunk(new_chunk_id, new_doc_id, source_chunk.content,
                                                     source_chunk.tokens, source_chunk.chunk_index, embedding)
                return imported_kb_count, imported_doc_count
            finally:
                target_session.close()
        finally:
            source_session.close()
            source_db = None

