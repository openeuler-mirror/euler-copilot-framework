"""flow Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pymongo import ASCENDING

from apps.constants import LOGGER
from apps.models.mongo import MongoDB
from apps.entities.enum_var import PermissionType


class AppManager:

    @staticmethod
    async def validate_user_app_access(user_sub: str, app_id: str) -> bool:
        """验证用户对应用的访问权限

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        try:
            app_collection = MongoDB.get_collection("app")  # 获取应用集合'
            match_conditions = [
                {"author": user_sub},
                {"permissions.type": PermissionType.PUBLIC.value},
                {
                    "$and": [
                        {"permissions.type": PermissionType.PROTECTED.value},
                        {"permissions.users": user_sub}
                    ]
                }
            ]
            query = {"$and": [{"_id": app_id},
                              {"$or": match_conditions}]}

            result = await app_collection.count_documents(query)
            return (result > 0)
        except Exception as e:
            LOGGER.error(f"Validate user app access failed due to: {e}")
            return False
