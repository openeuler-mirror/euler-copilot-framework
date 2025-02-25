"""应用中心 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import ray

from apps.constants import LOGGER
from apps.entities.appcenter import AppCenterCardItem, AppData
from apps.entities.collection import User
from apps.entities.enum_var import SearchType
from apps.entities.flow import AppMetadata, MetadataType, Permission
from apps.entities.pool import AppPool
from apps.entities.response_data import RecentAppList, RecentAppListItem
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.app import AppLoader


class AppCenterManager:
    """应用中心管理器"""

    class ModFavAppFlag(Enum):
        """收藏应用标志"""

        SUCCESS = 0
        NOT_FOUND = 1
        BAD_REQUEST = 2
        INTERNAL_ERROR = 3

    @staticmethod
    async def fetch_all_apps(
        user_sub: str,
        search_type: SearchType,
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[list[AppCenterCardItem], int]:
        """获取所有应用列表

        :param user_sub: 用户唯一标识
        :param search_type: 搜索类型
        :param keyword: 搜索关键字
        :param page: 页码
        :param page_size: 每页条数
        :return: 应用列表, 总应用数
        """
        try:
            # 搜索条件，仅显示已发布的应用
            base_filter = {"published": True}
            filters: dict[str, Any] = (
                AppCenterManager._build_filters(
                    {"published": True},
                    search_type,
                    keyword,
                )
                if keyword
                else base_filter
            )
            # 执行应用搜索
            apps, total_apps = await AppCenterManager._search_apps_by_filter(filters, page, page_size)
            fav_apps = await AppCenterManager._get_favorite_app_ids_by_user(user_sub)
            # 构建返回的应用卡片列表
            return [
                AppCenterCardItem(
                    appId=app.id,
                    icon=app.icon,
                    name=app.name,
                    description=app.description,
                    author=app.author,
                    favorited=(app.id in fav_apps),
                    published=app.published,
                )
                for app in apps
            ], total_apps

        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Get app list failed: {e}")
        return [], -1

    @staticmethod
    async def fetch_user_apps(
        user_sub: str,
        search_type: SearchType,
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[list[AppCenterCardItem], int]:
        """获取用户应用列表

        :param user_sub: 用户唯一标识
        :param search_type: 搜索类型
        :param keyword: 搜索关键词
        :param page: 页码
        :param page_size: 每页数量
        :return: 应用列表, 总应用数
        """
        try:
            # 搜索条件
            base_filter = {"author": user_sub}
            filters: dict[str, Any] = (
                AppCenterManager._build_filters(
                    base_filter,
                    search_type,
                    keyword,
                )
                if keyword and search_type != SearchType.AUTHOR
                else base_filter
            )
            apps, total_apps = await AppCenterManager._search_apps_by_filter(filters, page, page_size)
            fav_apps = await AppCenterManager._get_favorite_app_ids_by_user(user_sub)
            return [
                AppCenterCardItem(
                    appId=app.id,
                    icon=app.icon,
                    name=app.name,
                    description=app.description,
                    author=app.author,
                    favorited=(app.id in fav_apps),
                    published=app.published,
                )
                for app in apps
            ], total_apps
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Get app list by user failed: {e}")
        return [], -1

    @staticmethod
    async def fetch_favorite_apps(
        user_sub: str,
        search_type: SearchType,
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[list[AppCenterCardItem], int]:
        """获取用户收藏的应用列表

        :param user_sub: 用户唯一标识
        :param search_type: 搜索类型
        :param keyword: 搜索关键词
        :param page: 页码
        :param page_size: 每页数量
        :return: 应用列表，总应用数
        """
        try:
            fav_apps = await AppCenterManager._get_favorite_app_ids_by_user(user_sub)
            # 搜索条件
            base_filter = {
                "_id": {"$in": fav_apps},
                "published": True,
            }
            filters: dict[str, Any] = (
                AppCenterManager._build_filters(
                    base_filter,
                    search_type,
                    keyword,
                )
                if keyword
                else base_filter
            )
            apps, total_apps = await AppCenterManager._search_apps_by_filter(filters, page, page_size)
            return [
                AppCenterCardItem(
                    appId=app.id,
                    icon=app.icon,
                    name=app.name,
                    description=app.description,
                    author=app.author,
                    favorited=True,
                    published=app.published,
                )
                for app in apps
            ], total_apps
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Get favorite app list failed: {e}")
        return [], -1

    @staticmethod
    async def fetch_app_data_by_id(app_id: str) -> Optional[AppPool]:
        """根据应用ID获取应用元数据

        :param app_id: 应用ID
        :return: 应用元数据
        """
        try:
            app_collection = MongoDB.get_collection("app")
            db_data = await app_collection.find_one({"_id": app_id})
            if not db_data:
                LOGGER.warning(f"[AppCenterManager] No data found for app_id: {app_id}")
                return None
            return AppPool.model_validate(db_data)
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Get app metadata by app_id failed: {e}")
        return None

    @staticmethod
    async def create_app(user_sub: str, data: AppData) -> Optional[str]:
        """创建应用

        :param user_sub: 用户唯一标识
        :param data: 应用数据
        :return: 应用ID
        """
        app_id = str(uuid.uuid4())
        metadata = AppMetadata(
            type=MetadataType.APP,
            id=app_id,
            icon=data.icon,
            name=data.name,
            description=data.description,
            version="1.0.0",
            author=user_sub,
            links=data.links,
            first_questions=data.first_questions,
            history_len=data.history_len,
            permission=Permission(
                type=data.permission.type,
                users=data.permission.users or [],
            ),
        )
        try:
            app_loader = AppLoader.remote()
            await app_loader.save.remote(metadata, app_id)  # type: ignore[attr-type]
            ray.kill(app_loader)
            return app_id
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Create app failed: {e}")
        return None

    @staticmethod
    async def update_app(user_sub: str, app_id: str, data: AppData) -> bool:
        """更新应用

        :param app_id: 应用唯一标识
        :param data: 应用数据
        :return: 是否成功
        """
        metadata = AppMetadata(
            type=MetadataType.APP,
            id=app_id,
            icon=data.icon,
            name=data.name,
            description=data.description,
            version="1.0.0",
            author=user_sub,
            links=data.links,
            first_questions=data.first_questions,
            history_len=data.history_len,
            permission=Permission(
                type=data.permission.type,
                users=data.permission.users or [],
            ),
        )
        try:
            app_collection = MongoDB.get_collection("app")
            app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
            if not app_data:
                return False
            metadata.flows = app_data.flows
            metadata.published = app_data.published
            app_loader = AppLoader.remote()
            await app_loader.save.remote(metadata, app_id)  # type: ignore[attr-type]
            ray.kill(app_loader)
            return True
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Update app failed: {e}")
        return False

    @staticmethod
    async def publish_app(app_id: str) -> bool:
        """发布应用

        :param app_id: 应用唯一标识
        :return: 是否成功
        """
        try:
            app_collection = MongoDB.get_collection("app")
            await app_collection.update_one(
                {"_id": app_id},
                {"$set": {"published": True}},
            )
            return True
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Publish app failed: {e}")
        return False

    @staticmethod
    async def modify_favorite_app(app_id: str, user_sub: str, *, favorited: bool) -> ModFavAppFlag:
        """修改收藏状态

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param favorited: 是否收藏
        :return: 修改结果
        """
        try:
            app_collection = MongoDB.get_collection("app")
            user_collection = MongoDB.get_collection("user")
            db_data = await app_collection.find_one({"_id": app_id})
            if not db_data:
                return AppCenterManager.ModFavAppFlag.NOT_FOUND
            db_user = await user_collection.find_one({"_id": user_sub})
            if not db_user:
                return AppCenterManager.ModFavAppFlag.BAD_REQUEST
            user_data = User.model_validate(db_user)

            already_favorited = app_id in user_data.fav_apps
            if favorited == already_favorited:
                return AppCenterManager.ModFavAppFlag.BAD_REQUEST

            if favorited:
                await user_collection.update_one(
                    {"_id": user_sub},
                    {"$addToSet": {"fav_apps": app_id}},
                )
            else:
                await user_collection.update_one(
                    {"_id": user_sub},
                    {"$pull": {"fav_apps": app_id}},
                )
            return AppCenterManager.ModFavAppFlag.SUCCESS
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Modify favorite app failed: {e}")
        return AppCenterManager.ModFavAppFlag.INTERNAL_ERROR

    @staticmethod
    async def delete_app(app_id: str, user_sub: str) -> bool:
        """删除应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :return: 删除是否成功
        """
        try:
            app_collection = MongoDB.get_collection("app")
            app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
            if not app_data:
                return False
            if app_data.author != user_sub:
                return False
            # 删除应用
            app_loader = AppLoader.remote()
            await app_loader.delete.remote(app_id)  # type: ignore[attr-type]
            ray.kill(app_loader)
            user_collection = MongoDB.get_collection("user")
            # 删除用户使用记录
            await user_collection.update_many(
                {f"app_usage.{app_id}": {"$exists": True}},
                {"$unset": {f"app_usage.{app_id}": ""}},
            )
            # 删除用户收藏
            await user_collection.update_many(
                {"fav_apps": {"$in": [app_id]}},
                {"$pull": {"fav_apps": app_id}},
            )
            return True
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Delete app failed: {e}")
        return False

    @staticmethod
    async def get_recently_used_apps(count: int, user_sub: str) -> Optional[RecentAppList]:
        """获取用户最近使用的应用列表

        :param count: 应用数量
        :param user_sub: 用户唯一标识
        :return: 最近使用的应用列表
        """
        try:
            user_collection = MongoDB.get_collection("user")
            app_collection = MongoDB.get_collection("app")
            # 校验用户信息
            user_data = User.model_validate(await user_collection.find_one({"_id": user_sub}))
            # 获取最近使用的应用ID列表，按最后使用时间倒序排序
            # 允许 app_usage 为空
            usage_list = sorted(
                user_data.app_usage.items(),
                key=lambda x: x[1].last_used,
                reverse=True,
            )[:count]
            app_ids = [t[0] for t in usage_list]
            if not app_ids:
                apps = []  # 如果 app_ids 为空，直接返回空列表
            else:
                # 查询 MongoDB，获取符合条件的应用
                apps = await app_collection.find({"_id": {"$in": app_ids}}, {"name": 1}).to_list(len(app_ids))
            app_map = {str(a["_id"]): a.get("name", "") for a in apps}
            return RecentAppList(
                applications=[RecentAppListItem(appId=app_id, name=app_map.get(app_id, "")) for app_id in app_ids],
            )
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Get recently used apps failed: {e}")
        return None

    @staticmethod
    async def update_recent_app(user_sub: str, app_id: str) -> bool:
        """更新用户的最近使用应用列表

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :return: 更新是否成功
        """
        try:
            user_collection = MongoDB.get_collection("user")
            current_time = round(datetime.now(tz=timezone.utc).timestamp(), 3)
            result = await user_collection.update_one(
                {"_id": user_sub},  # 查询条件
                {
                    "$set": {
                        f"app_usage.{app_id}.last_used": current_time,  # 更新最后使用时间
                    },
                    "$inc": {
                        f"app_usage.{app_id}.count": 1,  # 增加使用次数
                    },
                },
                upsert=True,  # 如果 app_usage 字段或 app_id 不存在，则创建
            )
            if result.modified_count > 0 or result.upserted_id is not None:
                LOGGER.info(f"[AppCenterManager] Updated recent app for user {user_sub}: {app_id}")
                return True
            LOGGER.warning(f"[AppCenterManager] No changes made for user {user_sub}")
            return False
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Failed to update recent app: {e}")
            return False

    @staticmethod
    def _build_filters(
        base_filters: dict[str, Any],
        search_type: SearchType,
        keyword: str,
    ) -> dict[str, Any]:
        search_filters = [
            {"name": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
            {"author": {"$regex": keyword, "$options": "i"}},
        ]
        if search_type == SearchType.ALL:
            base_filters["$or"] = search_filters
        elif search_type == SearchType.NAME:
            base_filters["name"] = {"$regex": keyword, "$options": "i"}
        elif search_type == SearchType.DESCRIPTION:
            base_filters["description"] = {"$regex": keyword, "$options": "i"}
        elif search_type == SearchType.AUTHOR:
            base_filters["author"] = {"$regex": keyword, "$options": "i"}
        return base_filters

    @staticmethod
    async def _search_apps_by_filter(
        search_conditions: dict[str, Any],
        page: int,
        page_size: int,
    ) -> tuple[list[AppPool], int]:
        """根据过滤条件搜索应用并计算总页数"""
        try:
            app_collection = MongoDB.get_collection("app")
            total_apps = await app_collection.count_documents(search_conditions)
            db_data = (
                await app_collection.find(search_conditions)
                .sort("created_at", -1)
                .skip((page - 1) * page_size)
                .limit(page_size)
                .to_list(length=page_size)
            )
            apps = [AppPool.model_validate(doc) for doc in db_data]
            return apps, total_apps
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Search apps by filter failed: {e}")
        return [], -1

    @staticmethod
    async def _get_favorite_app_ids_by_user(user_sub: str) -> list[str]:
        """获取用户收藏的应用ID"""
        try:
            user_collection = MongoDB.get_collection("user")
            user_data = User.model_validate(await user_collection.find_one({"_id": user_sub}))
            return user_data.fav_apps
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Get favorite app ids by user_sub failed: {e}")
        return []
