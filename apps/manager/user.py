"""用户 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from typing import Optional

from apps.constants import LOGGER
from apps.entities.collection import User
from apps.manager.conversation import ConversationManager
from apps.models.mongo import MongoDB


class UserManager:
    """用户相关操作"""

    @staticmethod
    async def add_userinfo(user_sub: str) -> bool:
        """向数据库中添加用户信息

        :param user_sub: 用户sub
        :return: 是否添加成功
        """
        try:
            user_collection = MongoDB.get_collection("user")
            await user_collection.insert_one(User(
                _id=user_sub,
            ).model_dump(by_alias=True))
            return True
        except Exception as e:
            LOGGER.info(f"Add userinfo failed due to error: {e}")
            return False

    @staticmethod
    async def get_all_user_sub() -> list[str]:
        """获取所有用户的sub

        :return: 所有用户的sub列表
        """
        result = []
        try:
            user_collection = MongoDB.get_collection("user")
            result = [user["_id"] async for user in user_collection.find({}, {"_id": 1})]
        except Exception as e:
            LOGGER.info(f"Get all user_sub failed due to error: {e}")
        return result

    @staticmethod
    async def get_userinfo_by_user_sub(user_sub: str) -> Optional[User]:
        """根据用户sub获取用户信息

        :param user_sub: 用户sub
        :return: 用户信息
        """
        try:
            user_collection = MongoDB.get_collection("user")
            user_data = await user_collection.find_one({"_id": user_sub})
            return User(**user_data) if user_data else None
        except Exception as e:
            LOGGER.info(f"Get userinfo by user_sub failed due to error: {e}")
            return None

    @staticmethod
    async def update_userinfo_by_user_sub(user_sub: str, *, refresh_revision: bool = False) -> bool:
        """根据用户sub更新用户信息

        :param user_sub: 用户sub
        :param refresh_revision: 是否刷新revision
        :return: 更新后的用户信息
        """
        user_data = await UserManager.get_userinfo_by_user_sub(user_sub)
        if not user_data:
            return await UserManager.add_userinfo(user_sub)

        update_dict = {
            "$set": {"login_time": round(datetime.now(timezone.utc).timestamp(), 3)},
        }

        if refresh_revision:
            update_dict["$set"]["status"] = "init"  # type: ignore[assignment]
        try:
            user_collection = MongoDB.get_collection("user")
            result = await user_collection.update_one({"_id": user_sub}, update_dict)
            return result.modified_count > 0
        except Exception as e:
            LOGGER.info(f"Update userinfo by user_sub failed due to error: {e}")
            return False

    @staticmethod
    async def query_userinfo_by_login_time(login_time: float) -> list[str]:
        """根据登录时间获取用户sub

        :param login_time: 登录时间
        :return: 用户sub列表
        """
        try:
            user_collection = MongoDB.get_collection("user")
            return [user["_id"] async for user in user_collection.find({"login_time": {"$lt": login_time}}, {"_id": 1})]
        except Exception as e:
            LOGGER.info(f"Get userinfo by login_time failed due to error: {e}")
            return []

    @staticmethod
    async def delete_userinfo_by_user_sub(user_sub: str) -> bool:
        """根据用户sub删除用户信息

        :param user_sub: 用户sub
        :return: 是否删除成功
        """
        try:
            user_collection = MongoDB.get_collection("user")
            result = await user_collection.find_one_and_delete({"_id": user_sub})
            if not result:
                return False
            result = User.model_validate(result)

            for conv_id in result.conversations:
                await ConversationManager.delete_conversation_by_conversation_id(user_sub, conv_id)
            return True
        except Exception as e:
            LOGGER.info(f"Delete userinfo by user_sub failed due to error: {e}")
            return False
