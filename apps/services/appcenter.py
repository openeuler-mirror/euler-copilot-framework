# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""应用中心 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.common.mongo import MongoDB
from apps.constants import SERVICE_PAGE_SIZE
from apps.exceptions import InstancePermissionError
from apps.scheduler.pool.loader.app import AppLoader
from apps.schemas.agent import AgentAppMetadata
from apps.schemas.appcenter import AppCenterCardItem, AppData, AppPermissionData
from apps.schemas.collection import User
from apps.schemas.enum_var import AppFilterType, AppType, PermissionType
from apps.schemas.flow import AppMetadata, MetadataType, Permission
from apps.schemas.pool import AppPool
from apps.schemas.response_data import RecentAppList, RecentAppListItem
from apps.services.flow import FlowManager
from apps.services.mcp_service import MCPServiceManager

logger = logging.getLogger(__name__)


class AppCenterManager:
    """应用中心管理器"""

    @staticmethod
    async def fetch_apps(
        user_sub: str,
        keyword: str | None,
        app_type: AppType | None,
        page: int,
        filter_type: AppFilterType,
    ) -> tuple[list[AppCenterCardItem], int]:
        """
        获取应用列表

        :param user_sub: 用户唯一标识
        :param keyword: 搜索关键字
        :param app_type: 应用类型
        :param page: 页码
        :param filter_type: 过滤类型
        :return: 应用列表, 总应用数
        """
        filters: dict[str, Any] = {
            "$or": [
                {"permission.type": PermissionType.PUBLIC.value},
                {"$and": [
                    {"permission.type": PermissionType.PROTECTED.value},
                    {"permission.users": {"$in": [user_sub]}},
                ]},
                {"$and": [
                    {"permission.type": PermissionType.PRIVATE.value},
                    {"author": user_sub},
                ]},
            ],
        }

        user_favorite_app_ids = await AppCenterManager._get_favorite_app_ids_by_user(user_sub)
        if filter_type == AppFilterType.ALL:
            # 获取所有已发布的应用
            filters["published"] = True
        elif filter_type == AppFilterType.USER:
            # 获取用户创建的应用
            filters["author"] = user_sub
        elif filter_type == AppFilterType.FAVORITE:
            # 获取用户收藏的应用
            filters = {
                "_id": {"$in": user_favorite_app_ids},
                "published": True,
            }
        # 添加关键字搜索条件
        if keyword:
            filters["$or"] = [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
                {"author": {"$regex": keyword, "$options": "i"}},
            ]

        # 添加应用类型过滤条件
        if app_type is not None:
            filters["app_type"] = app_type.value
        # 获取应用列表
        apps, total_apps = await AppCenterManager._search_apps_by_filter(filters, page, SERVICE_PAGE_SIZE)

        # 构建返回的应用卡片列表
        app_cards = [
            AppCenterCardItem(
                appId=app.id,
                appType=app.app_type,
                icon=app.icon,
                name=app.name,
                description=app.description,
                author=app.author,
                favorited=(app.id in user_favorite_app_ids),
                published=app.published,
            )
            for app in apps
        ]

        return app_cards, total_apps

    @staticmethod
    async def fetch_app_data_by_id(app_id: str) -> AppPool:
        """
        根据应用ID获取应用元数据

        :param app_id: 应用唯一标识
        :return: 应用元数据
        """
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        db_data = await app_collection.find_one({"_id": app_id})
        if not db_data:
            msg = "应用不存在"
            raise ValueError(msg)
        return AppPool.model_validate(db_data)

    @staticmethod
    async def create_app(user_sub: str, data: AppData) -> str:
        """
        创建应用

        :param user_sub: 用户唯一标识
        :param data: 应用数据
        :return: 应用唯一标识
        """
        app_id = str(uuid.uuid4())
        await AppCenterManager._process_app_and_save(
            app_type=data.app_type,
            app_id=app_id,
            user_sub=user_sub,
            data=data,
        )
        return app_id

    @staticmethod
    async def update_app(user_sub: str, app_id: str, data: AppData) -> None:
        """
        更新应用

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :param data: 应用数据
        """
        # 获取应用数据并验证权限
        app_data = await AppCenterManager._get_app_data(app_id, user_sub)

        # 不允许更改应用类型
        if app_data.app_type != data.app_type:
            err = "不允许更改应用类型"
            raise ValueError(err)

        await AppCenterManager._process_app_and_save(
            app_type=data.app_type,
            app_id=app_id,
            user_sub=user_sub,
            data=data,
            app_data=app_data,
        )

    @staticmethod
    async def update_app_publish_status(app_id: str, user_sub: str) -> bool:
        """
        发布应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :return: 发布状态
        """
        # 获取应用数据并验证权限
        app_data = await AppCenterManager._get_app_data(app_id, user_sub)

        # 计算发布状态
        published = True
        for flow in app_data.flows:
            if not flow.debug:
                published = False
                break

        # 更新数据库
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        await app_collection.update_one(
            {"_id": app_id},
            {"$set": {"published": published}},
        )

        await AppCenterManager._process_app_and_save(
            app_type=app_data.app_type,
            app_id=app_id,
            user_sub=user_sub,
            app_data=app_data,
            published=published,
        )

        return published

    @staticmethod
    async def modify_favorite_app(app_id: str, user_sub: str, *, favorited: bool) -> None:
        """
        修改收藏状态

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param favorited: 是否收藏
        """
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        user_collection = mongo.get_collection("user")
        db_data = await app_collection.find_one({"_id": app_id})
        if not db_data:
            msg = "应用不存在"
            raise ValueError(msg)
        db_user = await user_collection.find_one({"_id": user_sub})
        if not db_user:
            msg = "用户不存在"
            raise ValueError(msg)
        user_data = User.model_validate(db_user)

        already_favorited = app_id in user_data.fav_apps
        if favorited == already_favorited:
            msg = "重复操作"
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
        """
        删除应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        """
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
        if not app_data:
            msg = "应用不存在"
            raise ValueError(msg)
        if app_data.author != user_sub:
            msg = "权限不足"
            raise InstancePermissionError(msg)
        # 删除应用
        await AppLoader.delete(app_id)
        # 删除应用相关的工作流
        for flow in app_data.flows:
            await FlowManager.delete_flow_by_app_and_flow_id(app_id, flow.id)

    @staticmethod
    async def get_recently_used_apps(count: int, user_sub: str) -> RecentAppList:
        """
        获取用户最近使用的应用列表

        :param count: 应用数量
        :param user_sub: 用户唯一标识
        :return: 最近使用的应用列表
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        app_collection = mongo.get_collection("app")
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
            apps = await app_collection.find({"_id": {"$in": app_ids}}, {"name": 1}).to_list(length=len(app_ids))
        app_map = {str(a["_id"]): a.get("name", "") for a in apps}
        return RecentAppList(
            applications=[RecentAppListItem(appId=app_id, name=app_map.get(app_id, "")) for app_id in app_ids],
        )

    @staticmethod
    async def update_recent_app(user_sub: str, app_id: str) -> bool:
        """
        更新用户的最近使用应用列表

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :return: 更新是否成功
        """
        if not app_id:
            return True
        try:
            mongo = MongoDB()
            user_collection = mongo.get_collection("user")
            current_time = round(datetime.now(UTC).timestamp(), 3)
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
        except Exception:
            logger.exception("[AppCenterManager] 更新用户最近使用应用失败")

        return False

    @staticmethod
    async def get_default_flow_id(app_id: str) -> str | None:
        """
        获取默认工作流ID

        :param app_id: 应用唯一标识
        :return: 默认工作流ID
        """
        try:
            mongo = MongoDB()
            app_collection = mongo.get_collection("app")
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
    async def _search_apps_by_filter(
        search_conditions: dict[str, Any],
        page: int,
        page_size: int,
    ) -> tuple[list[AppPool], int]:
        """根据过滤条件搜索应用并计算总页数"""
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
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

    @staticmethod
    async def _get_app_data(app_id: str, user_sub: str, *, check_permission: bool = True) -> AppPool:
        """
        从数据库获取应用数据并验证权限

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param check_permission: 是否检查权限
        :return: 应用数据
        :raises ValueError: 应用不存在
        :raises InstancePermissionError: 权限不足
        """
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        app_data = AppPool.model_validate(await app_collection.find_one({"_id": app_id}))
        if not app_data:
            msg = "应用不存在"
            raise ValueError(msg)
        if check_permission and app_data.author != user_sub:
            msg = "权限不足"
            raise InstancePermissionError(msg)
        return app_data

    @staticmethod
    def _build_common_metadata_params(app_id: str, user_sub: str, source: AppPool | AppData) -> dict:
        """构建元数据通用参数"""
        return {
            "type": MetadataType.APP,
            "id": app_id,
            "version": "1.0.0",
            "author": user_sub,
            "icon": source.icon,
            "name": source.name,
            "description": source.description,
            "history_len": source.history_len,
        }

    @staticmethod
    def _create_permission(permission_data: AppPermissionData) -> Permission:
        """创建权限对象"""
        return Permission(
            type=permission_data.type,
            users=permission_data.users or [],
        )

    @staticmethod
    def _create_flow_metadata(
        common_params: dict,
        data: AppData | None = None,
        app_data: AppPool | None = None,
        published: bool | None = None,
    ) -> AppMetadata:
        """创建工作流应用的元数据"""
        metadata = AppMetadata(**common_params)

        # 设置工作流应用特有属性
        if data:
            metadata.links = data.links
            metadata.first_questions = data.first_questions
        elif app_data:
            metadata.links = app_data.links
            metadata.first_questions = app_data.first_questions

        # 处理 'flows' 字段
        if app_data:
            # 更新场景 (update_app, update_app_publish_status):
            # 总是使用 app_data 中已存在的 flows。
            metadata.flows = app_data.flows
        else:
            # 创建场景 (create_app, app_data is None):
            # flows 默认为空列表。
            metadata.flows = []

        # 处理 'published' 字段
        if app_data:
            if published is None:  # 对应 update_app
                metadata.published = getattr(app_data, "published", False)
            else:  # 对应 update_app_publish_status
                metadata.published = published
        elif published is not None:  # 对应 _process_app_and_save 被直接调用且提供了 published，但无 app_data
            metadata.published = published
        else:  # 对应 create_app (app_data is None, published 参数为 None)
            metadata.published = False

        return metadata

    @staticmethod
    def _create_agent_metadata(
        common_params: dict,
        user_sub: str,
        data: AppData | None = None,
        app_data: AppPool | None = None,
        published: bool | None = None,
    ) -> AgentAppMetadata:
        """创建 Agent 应用的元数据"""
        metadata = AgentAppMetadata(**common_params)

        # mcp_service 逻辑
        if data is not None and hasattr(data, "mcp_service") and data.mcp_service:
            # 创建应用场景，验证传入的 mcp_service 状态，确保只使用已经激活的 (create_app)
            metadata.mcp_service = [svc for svc in data.mcp_service if MCPServiceManager.is_active(user_sub, svc)]
        elif data is not None and hasattr(data, "mcp_service"):
            # 更新应用场景，使用 data 中的 mcp_service (update_app)
            metadata.mcp_service = data.mcp_service if data.mcp_service is not None else []
        elif app_data is not None and hasattr(app_data, "mcp_service"):
            # 更新应用发布状态场景，使用 app_data 中的 mcp_service (update_app_publish_status)
            metadata.mcp_service = app_data.mcp_service if app_data.mcp_service is not None else []
        else:
            # 在预期的条件下，如果在 data 或 app_data 中找不到 mcp_service，则默认回退为空列表。
            metadata.mcp_service = []
        # 处理llm_id字段
        if data is not None and hasattr(data, "llm"):
            # 创建应用场景，验证传入的 llm_id 状态 (create_app)
            metadata.llm_id = data.llm if data.llm else "empty"
        elif app_data is not None and hasattr(app_data, "llm_id"):
            # 更新应用发布状态场景，使用 app_data 中的 llm_id (update_app_publish_status)
            metadata.llm_id = app_data.llm_id if app_data.llm_id else "empty"
        else:
            # 在预期的条件下，如果在 data 或 app_data 中找不到 llm_id，则默认回退为 "empty"。
            metadata.llm_id = "empty"
        # Agent 应用的发布状态逻辑
        if published is not None:  # 从 update_app_publish_status 调用，'published' 参数已提供
            metadata.published = published
        else:  # 从 create_app 或 update_app 调用 (此时传递给 _create_metadata 的 'published' 参数为 None)
            # 'published' 状态重置为 False。
            metadata.published = False

        return metadata

    @staticmethod
    async def _create_metadata(
        app_type: AppType,
        app_id: str,
        user_sub: str,
        **kwargs: Any,
    ) -> AppMetadata | AgentAppMetadata:
        """
        创建应用元数据

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param kwargs: 可选参数，包含:
            - data: 应用数据，用于新建或更新时提供
            - app_data: 现有应用数据，用于更新时提供
            - published: 发布状态，用于更新时提供
        :return: 应用元数据
        :raises ValueError: 无效应用类型或缺少必要数据
        """
        data: AppData | None = kwargs.get("data")
        app_data: AppPool | None = kwargs.get("app_data")
        published: bool | None = kwargs.get("published")

        # 验证必要数据
        source = data if data else app_data
        if not source:
            msg = "必须提供 data 或 app_data 参数"
            raise ValueError(msg)

        # 验证参数类型
        if data is not None and not isinstance(data, AppData):
            msg = f"参数 data 类型应为 AppData，但获取到的是 {type(data).__name__}"
            raise ValueError(msg)

        if app_data is not None and not isinstance(app_data, AppPool):
            msg = f"参数 app_data 类型应为 AppPool，但获取到的是 {type(app_data).__name__}"
            raise ValueError(msg)

        if published is not None and not isinstance(published, bool):
            msg = f"参数 published 类型应为 bool，但获取到的是 {type(published).__name__}"
            raise ValueError(msg)

        # 构建通用参数
        common_params = AppCenterManager._build_common_metadata_params(app_id, user_sub, source)

        # 设置权限
        if data:
            common_params["permission"] = AppCenterManager._create_permission(data.permission)
        elif app_data:
            common_params["permission"] = app_data.permission

        # 根据应用类型创建不同的元数据
        if app_type == AppType.FLOW:
            return AppCenterManager._create_flow_metadata(common_params, data, app_data, published)

        if app_type == AppType.AGENT:
            return AppCenterManager._create_agent_metadata(common_params, user_sub, data, app_data, published)

        msg = "无效的应用类型"
        raise ValueError(msg)

    @staticmethod
    async def _process_app_and_save(
        app_type: AppType,
        app_id: str,
        user_sub: str,
        **kwargs: Any,
    ) -> Any:
        """
        处理应用元数据创建和保存

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param kwargs: 其他可选参数(data, app_data, published)
        :return: 应用元数据
        """
        # 创建应用元数据
        metadata = await AppCenterManager._create_metadata(
            app_type=app_type,
            app_id=app_id,
            user_sub=user_sub,
            **kwargs,
        )

        # 保存应用
        app_loader = AppLoader()
        await app_loader.save(metadata, app_id)
        return metadata

    @staticmethod
    async def _get_favorite_app_ids_by_user(user_sub: str) -> list[str]:
        """获取用户收藏的应用ID"""
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        user_data = User.model_validate(await user_collection.find_one({"_id": user_sub}))
        return user_data.fav_apps
