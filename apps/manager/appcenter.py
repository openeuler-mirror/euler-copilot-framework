"""应用中心 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""
from datetime import datetime, timezone
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder

from apps.constants import LOGGER
from apps.entities.appcenter import AppCenterCardItem, AppData
from apps.entities.collection import User
from apps.entities.enum_var import SearchType
from apps.entities.flow import Permission
from apps.entities.pool import AppPool
from apps.entities.response_data import RecentAppList, RecentAppListItem
from apps.models.mongo import MongoDB


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
        """获取所有应用列表"""
        try:
            # 构建基础搜索条件
            filters: dict[str, Any] = {}

            if keyword and search_type != SearchType.AUTHOR:
                # 如果有关键词且不是按作者搜索，则使用原有的过滤逻辑
                filters = AppCenterManager._build_filters(
                    {"published": True},
                    search_type,
                    keyword,
                )
            else:
                # 修改为新的搜索条件：author=user_sub 或 published=True
                filters = {
                    "$or": [
                        {"author": user_sub},
                        {"published": True}
                    ]
                }

                # 如果有关键词且是按作者搜索，额外添加关键词过滤
                if keyword and search_type == SearchType.AUTHOR:
                    filters["$and"] = [
                        filters["$or"],
                        {"author": {"$regex": keyword, "$options": "i"}}
                    ]

            # 执行应用搜索
            apps, total_apps = await AppCenterManager._search_apps_by_filter(filters, page, page_size)

            # 构建返回的应用卡片列表
            return [
                AppCenterCardItem(
                    appId=app.id,
                    icon=app.icon,
                    name=app.name,
                    description=app.description,
                    author=app.author,
                    favorited=(user_sub in app.favorites),
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
        """获取用户应用列表"""
        try:
            # 搜索条件
            base_filter = {"author": user_sub}
            filters: dict[str, Any] = AppCenterManager._build_filters(
                base_filter,
                search_type,
                keyword,
            ) if keyword and search_type != SearchType.AUTHOR else base_filter
            apps, total_apps= await AppCenterManager._search_apps_by_filter(filters, page, page_size)
            return [
                AppCenterCardItem(
                    appId=app.id,
                    icon=app.icon,
                    name=app.name,
                    description=app.description,
                    author=app.author,
                    favorited=(user_sub in app.favorites),
                    published=app.published,
                )
                for app in apps
            ], total_apps
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Get app list by user failed: {e}")
        return [], -1

    @staticmethod
    async def fetch_favorite_apps(
        user_sub: str,
        search_type: SearchType,
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[list[AppCenterCardItem], int]:
        """获取用户收藏的应用列表"""
        try:
            fav_app = await AppCenterManager._get_favorite_app_ids_by_user(user_sub)
            # 搜索条件
            base_filter = {
                "_id": {"$in": fav_app},
                "published": True,
            }
            print(base_filter)
            filters: dict[str, Any] = AppCenterManager._build_filters(
                base_filter,
                search_type,
                keyword,
            ) if keyword else base_filter
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
            LOGGER.info(f"[AppCenterManager] Get favorite app list failed: {e}")
        return [], -1

    @staticmethod
    async def fetch_app_data_by_id(app_id: str) -> Optional[AppPool]:
        """根据应用ID获取应用元数据"""
        try:
            app_collection = MongoDB.get_collection("app")
            db_data = await app_collection.find_one({"_id": app_id})
            if not db_data:
                return None
            return AppPool.model_validate(db_data)
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Get app metadata by app_id failed: {e}")
        return None

    @staticmethod
    async def create_app(user_sub: str, data: AppData) -> Optional[str]:
        """创建应用"""
        app_id = str(uuid.uuid4())
        app = AppPool(
            _id=app_id,
            name=data.name,
            description=data.description,
            author=user_sub,
            icon=data.icon,
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
            await app_collection.insert_one(jsonable_encoder(app))
            return app_id
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Create app failed: {e}")
        return None

    @staticmethod
    async def update_app(app_id: str, data: AppData) -> bool:
        """更新应用"""
        try:
            app_collection = MongoDB.get_collection("app")
            app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
            if not app_data:
                return False
            # 如果工作流ID列表不一致，则需要取消发布状态
            published_false_needed = {flow.id for flow in app_data.flows} != set(data.workflows)
            update_data = {
                "name": data.name,
                "description": data.description,
                "icon": data.icon,
                "links": data.links,
                "first_questions": data.first_questions,
                "history_len": data.history_len,
                "permission": Permission(
                    type=data.permission.type,
                    users=data.permission.users or [],
                ),
            }
            if published_false_needed:
                update_data["published"] = False
            await app_collection.update_one({"_id": app_id}, {"$set": jsonable_encoder(update_data)})
            return True
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Update app failed: {e}")
        return False

    @staticmethod
    async def publish_app(app_id: str) -> bool:
        """发布应用"""
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
        """修改收藏状态"""
        try:
            app_collection = MongoDB.get_collection("app")
            db_data = await app_collection.find_one({"_id": app_id})
            if not db_data:
                return AppCenterManager.ModFavAppFlag.NOT_FOUND

            app_data = AppPool.model_validate(db_data)
            already_favorited = user_sub in app_data.favorites

            # 只能收藏未收藏的
            if favorited and already_favorited:
                return AppCenterManager.ModFavAppFlag.BAD_REQUEST
            # 只能取消已收藏的
            if not favorited and not already_favorited:
                return AppCenterManager.ModFavAppFlag.BAD_REQUEST

            if favorited:
                await app_collection.update_one(
                    {"_id": app_id},
                    {"$addToSet": {"favorites": user_sub}},
                    upsert=True,
                )
            else:
                await app_collection.update_one(
                    {"_id": app_id},
                    {"$pull": {"favorites": user_sub}},
                )
            return AppCenterManager.ModFavAppFlag.SUCCESS
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Modify favorite app failed: {e}")
        return AppCenterManager.ModFavAppFlag.INTERNAL_ERROR

    @staticmethod
    async def get_recently_used_apps(count: int, user_sub: str) -> Optional[RecentAppList]:
        """获取用户最近使用的应用列表"""
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
            apps = await app_collection.find(
                {"_id": {"$in": app_ids}}, {"name": 1}).to_list(len(app_ids))
            app_map = {str(a["_id"]): a.get("name", "") for a in apps}
            return RecentAppList(applications=[
                RecentAppListItem(appId=app_id, name=app_map.get(app_id, ""))
                for app_id in app_ids
            ])
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Get recently used apps failed: {e}")
        return None

    @staticmethod
    async def delete_app(app_id: str, user_sub: str) -> bool:
        """删除应用"""
        try:
            async with MongoDB.get_session() as session, await session.start_transaction():
                app_collection = MongoDB.get_collection("app")
                await app_collection.delete_one({"_id": app_id}, session=session)
                user_collection = MongoDB.get_collection("user")
                await user_collection.update_one(
                    {"_id": user_sub},
                    {"$unset": {f"app_usage.{app_id}": ""}},
                    session=session,
                )
                await session.commit_transaction()
                return True
        except Exception as e:
            LOGGER.error(f"[AppCenterManager] Delete app failed: {e}")
        return False

    @staticmethod
    async def update_recent_app(user_sub: str, app_id: str) -> bool:
        """更新用户的最近使用应用列表

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :return: 更新是否成功
        """
        try:
            # 获取 user 集合
            user_collection = MongoDB.get_collection("user")

            # 获取当前时间戳
            current_time = round(datetime.now(tz=timezone.utc).timestamp(), 3)

            # 更新用户的 app_usage 字段
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

            # 检查更新是否成功
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
            db_data = await app_collection.find(search_conditions) \
                .sort("created_at", -1) \
                .skip((page - 1) * page_size) \
                .limit(page_size) \
                .to_list(length=page_size)
            apps = [AppPool.model_validate(doc) for doc in db_data]
            return apps, total_apps
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Search apps by filter failed: {e}")
        return [], -1

    @staticmethod
    async def _get_favorite_app_ids_by_user(user_sub: str) -> list[str]:
        """获取用户收藏的应用ID"""
        try:
            app_collection = MongoDB.get_collection("app")
            cursor = app_collection.find({"favorites": user_sub})
            return [AppPool.model_validate(doc).id async for doc in cursor]
        except Exception as e:
            LOGGER.info(f"[AppCenterManager] Get favorite app ids by user_sub failed: {e}")
        return []
