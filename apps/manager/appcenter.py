"""应用中心 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from apps.entities.appcenter import AppCenterCardItem, AppData
from apps.entities.collection import User
from apps.entities.enum_var import SearchType
from apps.entities.flow import AppMetadata, MetadataType, Permission
from apps.entities.pool import AppPool
from apps.entities.response_data import RecentAppList, RecentAppListItem
from apps.manager.flow import FlowManager
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.app import AppLoader

logger = logging.getLogger(__name__)

class AppCenterManager:
    """应用中心管理器"""

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

        except Exception:
            logger.exception("[AppCenterManager] 获取应用列表失败")
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
        except Exception:
            logger.exception("[AppCenterManager] 获取用户应用列表失败")
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
        except Exception:
            logger.exception("[AppCenterManager] 获取用户收藏应用列表失败")
        return [], -1

    @staticmethod
    async def fetch_app_data_by_id(app_id: str) -> AppPool:
        """根据应用ID获取应用元数据

        :param app_id: 应用ID
        :return: 应用元数据
        """
        app_collection = MongoDB.get_collection("app")
        db_data = await app_collection.find_one({"_id": app_id})
        if not db_data:
            msg = "App not found"
            raise ValueError(msg)
        return AppPool.model_validate(db_data)

    @staticmethod
    async def create_app(user_sub: str, data: AppData) -> str:
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
            app_loader = AppLoader()
            await app_loader.save(metadata, app_id)
            return app_id
        except Exception:
            logger.exception("[AppCenterManager] 创建应用失败")
        return ""

    @staticmethod
    async def update_app(user_sub: str, app_id: str, data: AppData) -> None:
        """更新应用

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :param data: 应用数据
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
        app_collection = MongoDB.get_collection("app")
        app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
        if not app_data:
            msg = "App not found"
            raise ValueError(msg)
        if app_data.author != user_sub:
            msg = "Permission denied"
            raise PermissionError(msg)
        metadata.flows = app_data.flows
        metadata.published = app_data.published
        app_loader = AppLoader()
        await app_loader.save(metadata, app_id)

    @staticmethod
    async def publish_app(app_id: str, user_sub: str) -> None:
        """发布应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        """
        app_collection = MongoDB.get_collection("app")
        app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
        if not app_data:
            msg = "App not found"
            raise ValueError(msg)
        if app_data.author != user_sub:
            msg = "Permission denied"
            raise PermissionError(msg)
        await app_collection.update_one(
            {"_id": app_id},
            {"$set": {"published": True}},
        )

    @staticmethod
    async def modify_favorite_app(app_id: str, user_sub: str, *, favorited: bool) -> None:
        """修改收藏状态

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param favorited: 是否收藏
        """
        app_collection = MongoDB.get_collection("app")
        user_collection = MongoDB.get_collection("user")
        db_data = await app_collection.find_one({"_id": app_id})
        if not db_data:
            msg = "App not found"
            raise ValueError(msg)
        db_user = await user_collection.find_one({"_id": user_sub})
        if not db_user:
            msg = "User not found"
            raise ValueError(msg)
        user_data = User.model_validate(db_user)

        already_favorited = app_id in user_data.fav_apps
        if favorited == already_favorited:
            msg = "Duplicate operation"
            raise ValueError(msg)

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

    @staticmethod
    async def delete_app(app_id: str, user_sub: str) -> None:
        """删除应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        """
        app_collection = MongoDB.get_collection("app")
        app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
        if not app_data:
            msg = "App not found"
            raise ValueError(msg)
        if app_data.author != user_sub:
            msg = "Permission denied"
            raise PermissionError(msg)
        # 删除应用
        app_loader = AppLoader()
        await app_loader.delete(app_id)
        # 删除应用相关的工作流
        for flow in app_data.flows:
            await FlowManager.delete_flow_by_app_and_flow_id(app_id, flow.id)

    @staticmethod
    async def get_recently_used_apps(count: int, user_sub: str) -> RecentAppList:
        """获取用户最近使用的应用列表

        :param count: 应用数量
        :param user_sub: 用户唯一标识
        :return: 最近使用的应用列表
        """
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
                logger.info("[AppCenterManager] 更新用户最近使用应用: %s", user_sub)
                return True
            logger.warning("[AppCenterManager] 用户 %s 没有更新", user_sub)
            return False
        except Exception:
            logger.exception("[AppCenterManager] 更新用户最近使用应用失败")
            return False

    @staticmethod
    async def get_default_flow_id(app_id: str) -> Optional[str]:
        """获取默认工作流ID

        :param app_id: 应用ID
        :return: 默认工作流ID
        """
        try:
            app_collection = MongoDB.get_collection("app")
            db_data = await app_collection.find_one({"_id": app_id})
            if not db_data:
                logger.warning("[AppCenterManager] 应用不存在: %s", app_id)
                return None
            app_data = AppPool.model_validate(db_data)
            if not app_data.flows or len(app_data.flows) == 0:
                logger.warning("[AppCenterManager] 应用 %s 没有工作流", app_id)
                return None
            return app_data.flows[0].id
        except Exception:
            logger.exception("[AppCenterManager] 获取默认工作流ID失败")
        return None

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
        except Exception:
            logger.exception("[AppCenterManager] 根据过滤条件搜索应用失败")
        return [], -1

    @staticmethod
    async def _get_favorite_app_ids_by_user(user_sub: str) -> list[str]:
        """获取用户收藏的应用ID"""
        try:
            user_collection = MongoDB.get_collection("user")
            user_data = User.model_validate(await user_collection.find_one({"_id": user_sub}))
            return user_data.fav_apps
        except Exception:
            logger.exception("[AppCenterManager] 获取用户收藏应用ID失败")
        return []
