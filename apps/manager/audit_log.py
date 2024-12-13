# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from dataclasses import dataclass
import logging

from apps.models.mysql import AuditLog, MysqlDB

logger = logging.getLogger('gunicorn.error')


@dataclass
class AuditLogData:
    method_type: str
    source_name: str
    ip: str
    result: str
    reason: str


class AuditLogManager:
    def __init__(self):
        raise NotImplementedError("AuditLogManager无法被实例化")

    @staticmethod
    def add_audit_log(user_sub: str, data: AuditLogData):
        try:
            with MysqlDB().get_session() as session:
                add_audit_log = AuditLog(user_sub=user_sub, method_type=data.method_type,
                                         source_name=data.source_name, ip=data.ip,
                                         result=data.result, reason=data.reason)
                session.add(add_audit_log)
                session.commit()
        except Exception as e:
            logger.info(f"Add audit log failed due to error: {e}")
