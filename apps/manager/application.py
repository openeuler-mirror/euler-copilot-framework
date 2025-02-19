"""应用管理器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from apps.constants import LOGGER
from apps.entities.enum_var import PermissionType
from apps.models.mongo import MongoDB


class AppManager:
    """应用管理器"""

    @staticmethod
    async def validate_user_app_access(user_sub: str, app_id: str) -> bool:
        """验证用户对应用的访问权限

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        try:
            app_collection = MongoDB.get_collection("app")
            query = {
                "_id": app_id,
                "$or": [
                    {"author": user_sub},
                    {"permission.type": PermissionType.PUBLIC.value},
                    {
                        "$and": [
                            {"permission.type": PermissionType.PROTECTED.value},
                            {"permission.users": user_sub},
                        ],
                    },
                ],
            }

            result = await app_collection.find_one(query)
            return (result is not None)
        except Exception as e:
            LOGGER.error(f"Validate user app access failed due to: {e}")
            return False

    @staticmethod
    async def validate_app_belong_to_user(user_sub: str, app_id: str) -> bool:
        """验证用户对应用的属权

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果应用属于用户则返回True，否则返回False
        """
        try:
            app_collection = MongoDB.get_collection("app")  # 获取应用集合'
            query = {
                "_id": app_id,
                "author": user_sub,
            }

            result = await app_collection.find_one(query)
            return (result is not None)
        except Exception as e:
            LOGGER.error(f"Validate app belong to user failed due to: {e}")
            return False
