# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from datetime import datetime

import pytz
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, create_engine, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
import logging

from apps.common.config import config
from apps.common.singleton import Singleton

Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_sub = Column(String(length=100))
    revision_number = Column(String(length=100), nullable=True)
    login_time = Column(DateTime, nullable=True)
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    credit = Column(Integer, default=100)
    is_whitelisted = Column(Boolean, default=False)


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    conversation_id = Column(String(length=100), unique=True)
    summary = Column(Text, nullable=True)
    user_sub = Column(String(length=100))
    title = Column(String(length=200))
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))


class Record(Base):
    __tablename__ = "record"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    conversation_id = Column(String(length=100), index=True)
    record_id = Column(String(length=100))
    encrypted_question = Column(Text)
    question_encryption_config = Column(String(length=1000))
    encrypted_answer = Column(Text)
    answer_encryption_config = Column(String(length=1000))
    structured_output = Column(Text)
    flow_id = Column(String(length=100))
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    group_id = Column(String(length=100), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_sub = Column(String(length=100), nullable=True)
    method_type = Column(String(length=100), nullable=True)
    source_name = Column(String(length=100), nullable=True)
    ip = Column(String(length=100), nullable=True)
    result = Column(String(length=100), nullable=True)
    reason = Column(String(length=100), nullable=True)
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))


class Comment(Base):
    __tablename__ = "comment"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    record_id = Column(String(length=100), unique=True)
    is_like = Column(Boolean, nullable=True)
    dislike_reason = Column(String(length=100), nullable=True)
    reason_link = Column(String(length=200), nullable=True)
    reason_description = Column(String(length=500), nullable=True)
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    user_sub = Column(String(length=100), nullable=True)


class ApiKey(Base):
    __tablename__ = "api_key"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_sub = Column(String(length=100))
    api_key_hash = Column(String(length=16))
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))


class QuestionBlacklist(Base):
    __tablename__ = "blacklist"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    question = Column(Text)
    answer = Column(Text)
    is_audited = Column(Boolean, default=False)
    reason_description = Column(String(length=200))
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))


class Domain(Base):
    __tablename__ = "domain"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    domain_name = Column(String(length=100))
    domain_description = Column(Text)
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    updated_time = Column(DateTime)


class GiteeIDWhiteList(Base):
    __tablename__ = "gitee_id_white_list"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    gitee_id = Column(String(length=100))


class UserDomain(Base):
    __tablename__ = "user_domain"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_general_ci"
    }
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_sub = Column(String(length=100))
    domain_name = Column(String(length=100))
    domain_count = Column(Integer)
    created_time = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    updated_time = Column(DateTime)


class MysqlDB(metaclass=Singleton):

    def __init__(self):
        self.logger = logging.getLogger('gunicorn.error')
        try:
            self.engine = create_engine(
                f'mysql+pymysql://{config["MYSQL_USER"]}:{config["MYSQL_PWD"]}'
                f'@{config["MYSQL_HOST"]}/{config["MYSQL_DATABASE"]}',
                hide_parameters=True,
                echo=False,
                pool_recycle=300,
                pool_pre_ping=True)
            Base.metadata.create_all(self.engine)
        except Exception as e:
            self.logger.info(f"Error creating a session: {e}")

    def get_session(self):
        try:
            return sessionmaker(bind=self.engine)()
        except Exception as e:
            self.logger.info(f"Error creating a session: {e}")
            return None

    def close(self):
        try:
            self.engine.dispose()
        except Exception as e:
            self.logger.info(f"Error closing the engine: {e}")
