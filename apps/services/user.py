# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户 Manager"""

import logging
from datetime import UTC, datetime

from apps.schemas.request_data import UserUpdateRequest, UserPreferencesRequest
from apps.common.mongo import MongoDB
from apps.schemas.collection import User
from apps.schemas.preferences import UserPreferences
from apps.services.conversation import ConversationManager

logger = logging.getLogger(__name__)


class UserManager:
    """用户相关操作"""

    @staticmethod
    async def _handle_admin_user_creation(user_sub: str, user_name: str) -> str:
        """处理管理员用户创建时的user_sub逻辑（仅适用于Authelia）"""
        from apps.common.config import Config
        
        config = Config().get_config()
        
        # 只有在使用Authelia provider时才应用此逻辑
        if config.login.provider != "authelia":
            return user_sub
        
        # 检查是否启用了管理员配置且用户名匹配
        if not config.admin.enable or user_name != config.admin.user_name:
            return user_sub
        
        # 检查数据库中是否已存在管理员用户
        try:
            mongo = MongoDB()
            user_collection = mongo.get_collection("user")
            
            existing_admin = await user_collection.find_one({"_id": config.admin.user_sub})
            
            if existing_admin:
                # 数据库中已存在管理员用户，使用原始的user_sub
                logger.info(f"[_handle_admin_user_creation] 管理员用户已存在，使用原始user_sub: {user_sub}")
                return user_sub
            else:
                # 数据库中不存在管理员用户，使用配置的管理员user_sub
                logger.info(f"[_handle_admin_user_creation] 管理员用户不存在，使用配置的user_sub: {config.admin.user_sub}")
                return config.admin.user_sub
                
        except Exception as e:
            logger.error(f"[_handle_admin_user_creation] 检查管理员用户时出错: {e}")
            # 出错时使用原始的user_sub
            return user_sub

    @staticmethod
    async def add_userinfo(user_sub: str, user_name: str = "") -> None:
        """
        向数据库中添加用户信息

        :param user_sub: 用户sub
        :param user_name: 用户名
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        
        # 管理员用户特殊处理：检查是否应该使用配置的管理员user_sub
        final_user_sub = await UserManager._handle_admin_user_creation(user_sub, user_name)
        
        await user_collection.insert_one(User(
            _id=final_user_sub,
            user_name=user_name,
        ).model_dump(by_alias=True))

    @staticmethod
    async def get_all_user_sub(page_size: int = 20, page_cnt: int = 1, filter_user_subs: list[str] = []) -> tuple[list[str], int]:
        """
        获取所有用户的sub

        :return: 所有用户的sub列表
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        total = await user_collection.count_documents({}) - len(filter_user_subs)

        users = await user_collection.find(
            {"_id": {"$nin": filter_user_subs}},
            {"_id": 1},
        ).skip((page_cnt - 1) * page_size).limit(page_size).to_list(length=page_size)
        return [user["_id"] for user in users], total

    @staticmethod
    async def get_userinfo_by_user_sub(user_sub: str) -> User | None:
        """
        根据用户sub获取用户信息

        :param user_sub: 用户sub
        :return: 用户信息
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        user_data = await user_collection.find_one({"_id": user_sub})
        return User(**user_data) if user_data else None

    @staticmethod
    async def update_userinfo_by_user_sub(user_sub: str, data: UserUpdateRequest) -> None:
        """
        根据用户sub更新用户信息

        :param user_sub: 用户sub
        :param data: 用户更新信息
        :return: 是否更新成功
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        update_dict = {
            "$set": {
                "auto_execute": data.auto_execute,
            }
        }
        await user_collection.update_one({"_id": user_sub}, update_dict)

    @staticmethod
    async def update_refresh_revision_by_user_sub(user_sub: str, *, refresh_revision: bool = False, user_name: str = "") -> bool:
        """
        根据用户sub更新用户信息

        :param user_sub: 用户sub
        :param refresh_revision: 是否刷新revision
        :param user_name: 用户名（仅在创建新用户时使用）
        :return: 更新后的用户信息
        """
        mongo = MongoDB()
        user_data = await UserManager.get_userinfo_by_user_sub(user_sub)
        if not user_data:
            await UserManager.add_userinfo(user_sub, user_name)
            return True

        update_dict = {
            "$set": {"login_time": round(datetime.now(UTC).timestamp(), 3)},
        }

        if refresh_revision:
            update_dict["$set"]["status"] = "init"  # type: ignore[assignment]
        user_collection = mongo.get_collection("user")
        result = await user_collection.update_one({"_id": user_sub}, update_dict)
        return result.modified_count > 0

    @staticmethod
    async def query_userinfo_by_login_time(login_time: float) -> list[str]:
        """
        根据登录时间获取用户sub

        :param login_time: 登录时间
        :return: 用户sub列表
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        return [user["_id"] async for user in user_collection.find({"login_time": {"$lt": login_time}}, {"_id": 1})]

    @staticmethod
    async def delete_userinfo_by_user_sub(user_sub: str) -> None:
        """
        根据用户sub删除用户信息

        :param user_sub: 用户sub
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        result = await user_collection.find_one_and_delete({"_id": user_sub})
        if not result:
            return
        result = User.model_validate(result)

        for conv_id in result.conversations:
            await ConversationManager.delete_conversation_by_conversation_id(user_sub, conv_id)

    @staticmethod
    async def update_user_preferences_by_user_sub(user_sub: str, data: UserPreferencesRequest) -> None:
        """
        根据用户sub更新用户偏好设置

        :param user_sub: 用户sub
        :param data: 用户偏好设置更新信息
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        
        # 构建更新字典，只更新非None的字段，使用别名字段名以保持与模型一致
        preferences_update = {}
        if data.reasoning_model_preference is not None:
            preferences_update["preferences.reasoningModelPreference"] = data.reasoning_model_preference.model_dump(by_alias=True)
        if data.embedding_model_preference is not None:
            preferences_update["preferences.embeddingModelPreference"] = data.embedding_model_preference.model_dump(by_alias=True)
        if data.reranker_preference is not None:
            preferences_update["preferences.rerankerPreference"] = data.reranker_preference.model_dump(by_alias=True)
        if data.function_call_model_preference is not None:
            preferences_update["preferences.functionCallModelPreference"] = data.function_call_model_preference.model_dump(by_alias=True)
        if data.search_method_preference is not None:
            preferences_update["preferences.searchMethodPreference"] = data.search_method_preference
        if data.chain_of_thought_preference is not None:
            preferences_update["preferences.chainOfThoughtPreference"] = data.chain_of_thought_preference
        if data.auto_execute_preference is not None:
            preferences_update["preferences.autoExecutePreference"] = data.auto_execute_preference
        
        if preferences_update:
            update_dict = {"$set": preferences_update}
            await user_collection.update_one({"_id": user_sub}, update_dict)

    @staticmethod
    async def get_user_preferences_by_user_sub(user_sub: str) -> UserPreferences:
        """
        根据用户sub获取用户偏好设置

        :param user_sub: 用户sub
        :return: 用户偏好设置
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        user_data = await user_collection.find_one({"_id": user_sub}, {"preferences": 1})
        if user_data and "preferences" in user_data:
            preferences_data = user_data["preferences"]
            
            # 数据迁移：将旧的下划线格式字段名转换为驼峰格式
            migration_needed = False
            if "reasoning_model_preference" in preferences_data:
                preferences_data["reasoningModelPreference"] = preferences_data.pop("reasoning_model_preference")
                migration_needed = True
            if "embedding_model_preference" in preferences_data:
                preferences_data["embeddingModelPreference"] = preferences_data.pop("embedding_model_preference")
                migration_needed = True
            if "reranker_preference" in preferences_data:
                preferences_data["rerankerPreference"] = preferences_data.pop("reranker_preference")
                migration_needed = True
            if "function_call_model_preference" in preferences_data:
                preferences_data["functionCallModelPreference"] = preferences_data.pop("function_call_model_preference")
                migration_needed = True
            if "search_method_preference" in preferences_data:
                preferences_data["searchMethodPreference"] = preferences_data.pop("search_method_preference")
                migration_needed = True
            if "chain_of_thought_preference" in preferences_data:
                preferences_data["chainOfThoughtPreference"] = preferences_data.pop("chain_of_thought_preference")
                migration_needed = True
            if "auto_execute_preference" in preferences_data:
                preferences_data["autoExecutePreference"] = preferences_data.pop("auto_execute_preference")
                migration_needed = True
            
            # 如果进行了迁移，更新数据库
            if migration_needed:
                await user_collection.update_one(
                    {"_id": user_sub}, 
                    {"$set": {"preferences": preferences_data}}
                )
            
            # 使用model_validate来处理从数据库读取的数据，这样会正确处理别名映射
            return UserPreferences.model_validate(preferences_data)
        else:
            return UserPreferences()
