from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, 
    LargeBinary, Index, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = 'knowledge_bases'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    chunk_size = Column(Integer, nullable=False)
    embedding_model = Column(Text)
    embedding_endpoint = Column(Text)
    embedding_api_key = Column(Text)
    created_at = Column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, server_default=func.current_timestamp())
    
    # 关系
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_kb_name', 'name'),
    )


class Document(Base):
    """文档表"""
    __tablename__ = 'documents'
    
    id = Column(String, primary_key=True)
    kb_id = Column(String, ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=False)
    name = Column(String, nullable=False)
    file_path = Column(Text)
    file_type = Column(String)
    content = Column(Text)  # 文档完整内容
    chunk_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, server_default=func.current_timestamp())
    
    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_doc_kb_id', 'kb_id'),
        Index('idx_doc_name', 'name'),
    )


class Chunk(Base):
    """文档分块表"""
    __tablename__ = 'chunks'
    
    id = Column(String, primary_key=True)
    doc_id = Column(String, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    content = Column(Text, nullable=False)
    tokens = Column(Integer)
    chunk_index = Column(Integer)
    embedding = Column(LargeBinary)  # 向量嵌入
    created_at = Column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    
    # 关系
    document = relationship("Document", back_populates="chunks")
    
    # 索引
    __table_args__ = (
        Index('idx_chunk_doc_id', 'doc_id'),
        Index('idx_chunk_index', 'chunk_index'),
    )

