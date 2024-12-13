# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import hashlib
import logging
import uuid

from apps.entities.user import User as UserInfo
from apps.manager.user import UserManager
from apps.models.mysql import ApiKey, MysqlDB

logger = logging.getLogger('gunicorn.error')


class ApiKeyManager:
    def __init__(self):
        raise NotImplementedError("ApiKeyManager无法被实例化")

    @staticmethod
    def generate_api_key(userinfo: UserInfo) -> str | None:
        user_sub = userinfo.user_sub
        api_key = str(uuid.uuid4().hex)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            with MysqlDB().get_session() as session:
                session.add(ApiKey(user_sub=user_sub, api_key_hash=api_key_hash))
                session.commit()
        except Exception as e:
            logger.info(f"Add API key failed due to error: {e}")
            return None
        return api_key

    @staticmethod
    def delete_api_key(userinfo: UserInfo) -> bool:
        user_sub = userinfo.user_sub
        if not ApiKeyManager.api_key_exists(userinfo):
            return False
        try:
            with MysqlDB().get_session() as session:
                session.query(ApiKey).filter(ApiKey.user_sub == user_sub).delete()
                session.commit()
        except Exception as e:
            logger.info(f"Delete API key failed due to error: {e}")
            return False
        else:
            return True

    @staticmethod
    def api_key_exists(userinfo: UserInfo) -> bool:
        user_sub = userinfo.user_sub
        try:
            with MysqlDB().get_session() as session:
                result = session.query(ApiKey).filter(ApiKey.user_sub == user_sub).first()
        except Exception as e:
            logger.info(f"Check API key existence failed due to error: {e}")
            return False
        else:
            return result is not None

    @staticmethod
    def get_user_by_api_key(api_key: str) -> UserInfo | None:
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            with MysqlDB().get_session() as session:
                user_sub = session.query(ApiKey).filter(ApiKey.api_key_hash == api_key_hash).first().user_sub
            if user_sub is None:
                return None
            userdata = UserManager.get_userinfo_by_user_sub(user_sub)
            if userdata is None:
                return None
        except Exception as e:
            logger.info(f"Get user info by API key failed due to error: {e}")
        else:
            return UserInfo(user_sub=userdata.user_sub, revision_number=userdata.revision_number)

    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            with MysqlDB().get_session() as session:
                user_sub = session.query(ApiKey).filter(ApiKey.api_key_hash == api_key_hash).first().user_sub
        except Exception as e:
            logger.info(f"Verify API key failed due to error: {e}")
            return False
        return user_sub is not None

    @staticmethod
    def update_api_key(userinfo: UserInfo) -> str | None:
        if not ApiKeyManager.api_key_exists(userinfo):
            return None
        user_sub = userinfo.user_sub
        api_key = str(uuid.uuid4().hex)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        try:
            with MysqlDB().get_session() as session:
                session.query(ApiKey).filter(ApiKey.user_sub == user_sub).update({"api_key_hash": api_key_hash})
                session.commit()
        except Exception as e:
            logger.info(f"Update API key failed due to error: {e}")
            return None
        return api_key
