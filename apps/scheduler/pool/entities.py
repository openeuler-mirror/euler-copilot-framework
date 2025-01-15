"""内存SQLite中的表结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from sqlalchemy import Column, Integer, LargeBinary, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class FlowItem(Base):
    """Flow数据表"""

    __tablename__ = "flow"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin = Column(String(length=100), nullable=False)
    name = Column(String(length=100), nullable=False, unique=True)
    description = Column(String(length=1500), nullable=False)


class PluginItem(Base):
    """Plugin数据表"""

    __tablename__ = "plugin"
    id = Column(String(length=100), primary_key=True, nullable=False, unique=True)
    show_name = Column(String(length=100), nullable=False, unique=True)
    description = Column(String(length=1500), nullable=False)
    auth = Column(String(length=500), nullable=True)
    spec = Column(LargeBinary, nullable=False)
    signature = Column(String(length=100), nullable=False)


class CallItem(Base):
    """Call数据表"""

    __tablename__ = "call"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plugin = Column(String(length=100), nullable=True)
    name = Column(String(length=100), nullable=False)
    description = Column(String(length=1500), nullable=False)
