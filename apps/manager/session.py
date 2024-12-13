# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from typing import Any, Dict

from apps.common.config import config
from apps.entities.user import User
from apps.manager.blacklist import UserBlacklistManager
from apps.manager.user import UserManager
from apps.models.redis import RedisConnectionPool

logger = logging.getLogger("gunicorn.error")


class SessionManager:
    def __init__(self):
        raise NotImplementedError("SessionManager不可以被实例化")

    @staticmethod
    def create_session(ip: str , extra_keys: Dict[str, Any] | None = None) -> str:
        session_id = secrets.token_hex(16)
        data = {
            "ip": ip
        }
        if config["DISABLE_LOGIN"]:
            data.update({
                "user_sub": config["DEFAULT_USER"]
            })

        if extra_keys is not None:
            data.update(extra_keys)
        with RedisConnectionPool.get_redis_connection() as r:
            try:
                r.hmset(session_id, data)
                r.expire(session_id, config["SESSION_TTL"] * 60)
            except Exception as e:
                logger.error(f"Session error: {e}")
        return session_id

    @staticmethod
    def delete_session(session_id: str) -> bool:
        if not session_id:
            return True
        with RedisConnectionPool.get_redis_connection() as r:
            try:
                if not r.exists(session_id):
                    return True
                num = r.delete(session_id)
                if num != 1:
                    return True
                return False
            except Exception as e:
                logger.error(f"Delete session error: {e}")
                return False

    @staticmethod
    def get_session(session_id: str, session_ip: str) -> str:
        if not session_id:
            session_id = SessionManager.create_session(session_ip)
            return session_id

        ip = None
        with RedisConnectionPool.get_redis_connection() as r:
            try:
                ip = r.hget(session_id, "ip").decode()
                r.expire(session_id, config["SESSION_TTL"] * 60)
            except Exception as e:
                logger.error(f"Read session error: {e}")

            return session_id

    @staticmethod
    def verify_user(session_id: str) -> bool:
        with RedisConnectionPool.get_redis_connection() as r:
            try:
                user_exist = r.hexists(session_id, "user_sub")
                r.expire(session_id, config["SESSION_TTL"] * 60)
                return user_exist
            except Exception as e:
                logger.error(f"User not in session: {e}")
                return False

    @staticmethod
    def get_user(session_id: str) -> User | None:
        # 从session_id查询user_sub
        with RedisConnectionPool.get_redis_connection() as r:
            try:
                user_sub = r.hget(session_id, "user_sub")
                r.expire(session_id, config["SESSION_TTL"] * 60)
            except Exception as e:
                logger.error(f"Get user from session error: {e}")
                return None

        # 查询黑名单
        if UserBlacklistManager.check_blacklisted_users(user_sub):
            logger.error("User in session blacklisted.")
            with RedisConnectionPool.get_redis_connection() as r:
                try:
                    r.hdel(session_id, "user_sub")
                    r.expire(session_id, config["SESSION_TTL"] * 60)
                    return None
                except Exception as e:
                    logger.error(f"Delete user from session error: {e}")
                    return None

        user = UserManager.get_userinfo_by_user_sub(user_sub)
        return User(user_sub=user.user_sub, revision_number=user.revision_number)

    @staticmethod
    def create_csrf_token(session_id: str) -> str | None:
        rand = secrets.token_hex(8)

        with RedisConnectionPool.get_redis_connection() as r:
            try:
                r.hset(session_id, "nonce", rand)
                r.expire(session_id, config["SESSION_TTL"] * 60)
            except Exception as e:
                logger.error(f"Create csrf token from session error: {e}")
                return None

        csrf_value = f"{session_id}{rand}"
        csrf_b64 = base64.b64encode(bytes.fromhex(csrf_value))

        hmac_processor = hmac.new(key=bytes.fromhex(config["JWT_KEY"]), msg=csrf_b64, digestmod=hashlib.sha256)
        signature = base64.b64encode(hmac_processor.digest())

        csrf_b64 = csrf_b64.decode("utf-8")
        signature = signature.decode("utf-8")
        return f"{csrf_b64}.{signature}"

    @staticmethod
    def verify_csrf_token(session_id: str, token: str) -> bool:
        if not token:
            return False

        token_msg = token.split(".")
        if len(token_msg) != 2:
            return False

        first_part = base64.b64decode(token_msg[0]).hex()
        current_session_id = first_part[:32]
        logger.error(f"current_session_id: {current_session_id}, session_id: {session_id}")
        if current_session_id != session_id:
            return False

        current_nonce = first_part[32:]
        with RedisConnectionPool.get_redis_connection() as r:
            try:
                nonce = r.hget(current_session_id, "nonce")
                if nonce != current_nonce:
                    return False
                r.expire(current_session_id, config["SESSION_TTL"] * 60)
            except Exception as e:
                logger.error(f"Get csrf token from session error: {e}")

        hmac_obj = hmac.new(key=bytes.fromhex(config["JWT_KEY"]),
                            msg=token_msg[0].encode("utf-8"), digestmod=hashlib.sha256)
        signature = hmac_obj.digest()
        current_signature = base64.b64decode(token_msg[1])

        return hmac.compare_digest(signature, current_signature)
