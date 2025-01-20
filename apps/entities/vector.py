"""向量数据库数据结构；数据将存储在PostgreSQL中

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AppVector(Base):
    """App向量信息"""

    __tablename__ = "flow_vector"
    id = Column(String(length=100), primary_key=True, nullable=False, unique=True)
    embedding = Column(Vector(1024), nullable=False)


class ServiceVector(Base):
    """Service向量信息"""

    __tablename__ = "service_vector"
    id = Column(String(length=100), primary_key=True, nullable=False, unique=True)
    embedding = Column(Vector(1024), nullable=False)


class NodeVector(Base):
    """Node向量信息"""

    __tablename__ = "node_vector"
    id = Column(String(length=100), primary_key=True, nullable=False, unique=True)
    embedding = Column(Vector(1024), nullable=False)
