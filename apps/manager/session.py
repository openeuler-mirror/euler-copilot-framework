"""浏览器Session Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import base64
import hashlib
import hmac
import secrets
from typing import Any, Optional

from apps.common.config import config
from apps.constants import LOGGER
from apps.manager.blacklist import UserBlacklistManager
from apps.models.redis import RedisConnectionPool


class SessionManager:
    """浏览器Session管理"""

    @staticmethod
    async def create_session(ip: Optional[str] = None, extra_keys: Optional[dict[str, Any]] = None) -> str:
        """创建浏览器Session"""
        if not ip:
            err = "用户IP错误！"
            raise ValueError(err)

        session_id = secrets.token_hex(16)
        data = {
            "ip": ip,
        }
        if config["DISABLE_LOGIN"]:
            data.update({
                "user_sub": config["DEFAULT_USER"],
            })

        if extra_keys is not None:
            data.update(extra_keys)
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.hmset(session_id, data)
                pipe.expire(session_id, config["SESSION_TTL"] * 60)
                await pipe.execute()
            except Exception as e:
                LOGGER.error(f"Session error: {e}")
        return session_id

    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """删除浏览器Session"""
        if not session_id:
            return True
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.exists(session_id)
                result = await pipe.execute()
                if not result[0]:
                    return True
                pipe.delete(session_id)
                result = await pipe.execute()
                return result[0] != 1
            except Exception as e:
                LOGGER.error(f"Delete session error: {e}")
                return False

    @staticmethod
    async def get_session(session_id: str, session_ip: str) -> str:
        """获取浏览器Session"""
        if not session_id:
            return await SessionManager.create_session(session_ip)

        ip = None
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.hget(session_id, "ip")
                pipe.expire(session_id, config["SESSION_TTL"] * 60)
                result = await pipe.execute()
                ip = result[0].decode()
            except Exception as e:
                LOGGER.error(f"Read session error: {e}")

        if not ip or ip != session_ip:
            return await SessionManager.create_session(session_ip)
        return session_id

    @staticmethod
    async def verify_user(session_id: str) -> bool:
        """验证用户是否在Session中"""
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.hexists(session_id, "user_sub")
                pipe.expire(session_id, config["SESSION_TTL"] * 60)
                result = await pipe.execute()
                return result[0]
            except Exception as e:
                LOGGER.error(f"User not in session: {e}")
                return False

    @staticmethod
    async def get_user(session_id: str) -> Optional[str]:
        """从Session中获取用户"""
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.hget(session_id, "user_sub")
                pipe.expire(session_id, config["SESSION_TTL"] * 60)
                result = await pipe.execute()
                user_sub = result[0].decode()
            except Exception as e:
                LOGGER.error(f"Get user from session error: {e}")
                return None

        # 查询黑名单
        if await UserBlacklistManager.check_blacklisted_users(user_sub):
            LOGGER.error("User in session blacklisted.")
            async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
                try:
                    pipe.hdel(session_id, "user_sub")
                    pipe.expire(session_id, config["SESSION_TTL"] * 60)
                    await pipe.execute()
                    return None
                except Exception as e:
                    LOGGER.error(f"Delete user from session error: {e}")
                    return None

        return user_sub

    @staticmethod
    async def create_csrf_token(session_id: str) -> str:
        """创建CSRF Token"""
        rand = secrets.token_hex(8)

        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.hset(session_id, "nonce", rand)
                pipe.expire(session_id, config["SESSION_TTL"] * 60)
                await pipe.execute()
            except Exception as e:
                err = f"Create csrf token from session error: {e}"
                raise RuntimeError(err) from e

        csrf_value = f"{session_id}{rand}"
        csrf_b64 = base64.b64encode(bytes.fromhex(csrf_value))

        jwt_key = base64.b64decode(config["JWT_KEY"])
        hmac_processor = hmac.new(key=jwt_key, msg=csrf_b64, digestmod=hashlib.sha256)
        signature = base64.b64encode(hmac_processor.digest())

        csrf_b64 = csrf_b64.decode("utf-8")
        signature = signature.decode("utf-8")
        return f"{csrf_b64}.{signature}"

    @staticmethod
    async def verify_csrf_token(session_id: str, token: str) -> bool:
        """验证CSRF Token"""
        if not token:
            return False

        token_msg = token.split(".")
        if len(token_msg) != 2:  # noqa: PLR2004
            return False

        first_part = base64.b64decode(token_msg[0]).hex()
        current_session_id = first_part[:32]
        LOGGER.error(f"current_session_id: {current_session_id}, session_id: {session_id}")
        if current_session_id != session_id:
            return False

        current_nonce = first_part[32:]
        async with RedisConnectionPool.get_redis_connection().pipeline(transaction=True) as pipe:
            try:
                pipe.hget(current_session_id, "nonce")
                pipe.expire(current_session_id, config["SESSION_TTL"] * 60)
                result = await pipe.execute()
                nonce = result[0].decode()
                if nonce != current_nonce:
                    return False
            except Exception as e:
                LOGGER.error(f"Get csrf token from session error: {e}")

        jwt_key = base64.b64decode(config["JWT_KEY"])
        hmac_obj = hmac.new(key=jwt_key, msg=token_msg[0].encode("utf-8"), digestmod=hashlib.sha256)
        signature = hmac_obj.digest()
        current_signature = base64.b64decode(token_msg[1])

        return hmac.compare_digest(signature, current_signature)
