# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""应用管理器"""

import logging

from apps.common.mongo import MongoDB
from apps.schemas.enum_var import PermissionType

logger = logging.getLogger(__name__)


class AppManager:
    """应用管理器"""

    @staticmethod
    async def validate_user_app_access(user_sub: str, app_id: str) -> bool:
        """
        验证用户对应用的访问权限

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
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
        return result is not None

    @staticmethod
    async def validate_app_belong_to_user(user_sub: str, app_id: str) -> bool:
        """
        验证用户对应用的属权

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果应用属于用户则返回True，否则返回False
        """
        app_collection = MongoDB.get_collection("app")  # 获取应用集合'
        query = {
            "_id": app_id,
            "author": user_sub,
        }

        result = await app_collection.find_one(query)
        return result is not None
