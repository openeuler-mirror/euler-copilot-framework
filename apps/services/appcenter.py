# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""应用中心 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select

from apps.common.postgres import postgres
from apps.constants import APP_DEFAULT_HISTORY_LEN, SERVICE_PAGE_SIZE
from apps.exceptions import InstancePermissionError
from apps.models import (
    App,
    AppACL,
    AppType,
    PermissionType,
    UserAppUsage,
    UserFavorite,
    UserFavoriteType,
)
from apps.scheduler.pool.pool import pool
from apps.schemas.appcenter import (
    AppCenterCardItem,
    AppData,
    RecentAppList,
    RecentAppListItem,
)
from apps.schemas.enum_var import AppFilterType
from apps.schemas.flow import AgentAppMetadata, FlowAppMetadata, MetadataType, Permission

from .flow import FlowManager
from .mcp_service import MCPServiceManager
from .user import UserManager

logger = logging.getLogger(__name__)


class AppCenterManager:
    """应用中心管理器"""

    @staticmethod
    async def validate_user_app_access(user_id: str, app_id: uuid.UUID) -> bool:
        """
        验证用户对应用的访问权限

        :param user_id: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        async with postgres.session() as session:
            sql = select(App.authorId, App.permission).where(App.id == app_id)
            app_info = (await session.execute(sql)).one_or_none()
            if not app_info:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)

            if app_info.authorId == user_id:
                return True

            if app_info.permission == PermissionType.PUBLIC:
                return True
            if app_info.permission == PermissionType.PRIVATE:
                return False
            if app_info.permission == PermissionType.PROTECTED:
                sql = select(AppACL.appId).where(
                    AppACL.appId == app_id,
                    AppACL.userId == user_id,
                )
                acl_info = (await session.execute(sql)).one_or_none()
                if acl_info:
                    return True
            return False


    @staticmethod
    async def validate_app_belong_to_user(user_id: str, app_id: uuid.UUID) -> bool:
        """
        验证用户对应用的属权

        :param user_id: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果应用属于用户则返回True，否则返回False
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(
                    and_(
                        App.id == app_id,
                        App.authorId == user_id,
                    ),
                ),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在或权限不足: {app_id}"
                raise ValueError(msg)
            return True


    @staticmethod
    async def fetch_apps(
        user_id: str,
        keyword: str | None,
        app_type: AppType | None,
        page: int,
        filter_type: AppFilterType,
    ) -> tuple[list[AppCenterCardItem], int]:
        """
        获取应用列表

        :param user_id: 用户唯一标识
        :param keyword: 搜索关键字
        :param app_type: 应用类型
        :param page: 页码
        :param filter_type: 过滤类型
        :return: 应用列表, 总应用数
        """
        async with postgres.session() as session:
            protected_apps = select(AppACL.appId).where(
                AppACL.userId == user_id,
            )
            app_data = select(App).where(
                or_(
                    App.permission == PermissionType.PUBLIC,
                    and_(
                        App.permission == PermissionType.PRIVATE,
                        App.authorId == user_id,
                    ),
                    and_(
                        App.permission == PermissionType.PROTECTED,
                        App.id.in_(protected_apps),
                    ),
                ),
            ).cte()

            favapps_sql = select(UserFavorite.itemId).where(
                and_(
                    UserFavorite.userId == user_id,
                    UserFavorite.favouriteType == UserFavoriteType.APP,
                ),
            )
            favapps = list((await session.scalars(favapps_sql)).all())

            if filter_type == AppFilterType.ALL:
                filtered_apps = select(app_data).where(app_data.c.isPublished == True).cte()  # noqa: E712
            elif filter_type == AppFilterType.USER:
                filtered_apps = select(app_data).where(app_data.c.authorId == user_id).cte()
            elif filter_type == AppFilterType.FAVORITE:
                filtered_apps = select(app_data).where(
                    and_(
                        app_data.c.id.in_(favapps_sql),
                        app_data.c.isPublished == True,  # noqa: E712
                    ),
                ).cte()

            if app_type is not None:
                type_apps = select(filtered_apps).where(filtered_apps.c.appType == AppType(app_type)).cte()
            else:
                type_apps = filtered_apps

            if keyword:
                # 通过 userName 关键词搜索作者
                author_ids = await UserManager.get_user_ids_by_username_keyword(keyword)
                conditions = [
                    type_apps.c.name.ilike(f"%{keyword}%"),
                    type_apps.c.description.ilike(f"%{keyword}%"),
                ]
                if author_ids:
                    conditions.append(type_apps.c.authorId.in_(author_ids))
                keyword_apps = select(type_apps).where(or_(*conditions)).cte()
            else:
                keyword_apps = type_apps

            total_apps = (await session.scalars(
                select(func.count()).select_from(keyword_apps),
            )).one()
            result = list((await session.execute(
                select(keyword_apps).order_by(keyword_apps.c.updatedAt.desc())
                .offset((page - 1) * SERVICE_PAGE_SIZE).limit(SERVICE_PAGE_SIZE),
            )).all())

            # 批量获取所有作者的用户名
            author_ids = {row.authorId for row in result}
            author_names = await UserManager.get_usernames_by_ids(author_ids)

            app_cards = []
            for row in result:
                app_cards += [AppCenterCardItem(
                    appId=row.id,
                    appType=row.appType,
                    icon=row.icon,
                    name=row.name,
                    description=row.description,
                    author=author_names[row.authorId],
                    favorited=(row.id in favapps),
                    published=row.isPublished,
                )]

        return app_cards, total_apps


    @staticmethod
    async def fetch_app_metadata_by_id(app_id: uuid.UUID) -> FlowAppMetadata | AgentAppMetadata:
        """
        根据应用ID获取应用元数据（先检查数据库，再使用Loader）

        :param app_id: 应用唯一标识
        :return: 应用元数据
        """
        async with postgres.session() as session:
            app_exists = (await session.scalars(
                select(App.id).where(App.id == app_id),
            )).one_or_none()
            if not app_exists:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)

        try:
            return await pool.app_loader.read_metadata(app_id)
        except ValueError as e:
            msg = f"[AppCenterManager] 应用元数据文件不存在: {app_id}"
            raise ValueError(msg) from e


    @staticmethod
    async def create_app(user_id: str, data: AppData) -> uuid.UUID:
        """
        创建应用

        :param user_id: 用户唯一标识
        :param data: 应用数据
        :return: 应用唯一标识
        """
        app_id = uuid.uuid4()
        await AppCenterManager._process_app_and_save(
            app_type=data.app_type,
            app_id=app_id,
            user_id=user_id,
            data=data,
        )
        return app_id


    @staticmethod
    async def update_app(user_id: str, app_id: uuid.UUID, data: AppData) -> None:
        """
        更新应用

        :param user_id: 用户唯一标识
        :param app_id: 应用唯一标识
        :param data: 应用数据
        """
        app_data = await AppCenterManager._get_app_data(app_id, user_id)

        if app_data.appType != data.app_type:
            err = f"【AppCenterManager】不允许更改应用类型: {app_data.appType} -> {data.app_type}"
            raise ValueError(err)

        await AppCenterManager._process_app_and_save(
            app_type=data.app_type,
            app_id=app_id,
            user_id=user_id,
            data=data,
            published=None,
        )


    @staticmethod
    async def update_app_publish_status(app_id: uuid.UUID, user_id: str) -> bool:
        """
        发布应用

        :param app_id: 应用唯一标识
        :param user_id: 用户唯一标识
        :return: 发布状态
        """
        app_data = await AppCenterManager._get_app_data(app_id, user_id)

        flows = await FlowManager.get_flows_by_app_id(app_id)
        published = True
        for flow in flows:
            if not flow.debug:
                published = False
                break

        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)
            app_obj.isPublished = published
            await session.merge(app_obj)
            await session.commit()

        await AppCenterManager._process_app_and_save(
            app_type=app_data.appType,
            app_id=app_id,
            user_id=user_id,
            data=None,
            published=published,
        )
        return published


    @staticmethod
    async def modify_favorite_app(app_id: uuid.UUID, user_id: str, *, favorited: bool) -> None:
        """
        修改收藏状态

        :param app_id: 应用唯一标识
        :param user_id: 用户唯一标识
        :param favorited: 是否收藏
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)

            app_favorite = (await session.scalars(
                select(UserFavorite).where(
                    and_(
                        UserFavorite.userId == user_id,
                        UserFavorite.itemId == app_id,
                        UserFavorite.favouriteType == UserFavoriteType.APP,
                    ),
                ),
            )).one_or_none()
            if not app_favorite and favorited:
                app_favorite = UserFavorite(
                    userId=user_id,
                    favouriteType=UserFavoriteType.APP,
                    itemId=app_id,
                )
                session.add(app_favorite)
            elif app_favorite and not favorited:
                await session.delete(app_favorite)
            else:
                msg = f"[AppCenterManager] 重复操作: {app_id}"
                raise ValueError(msg)


    @staticmethod
    async def delete_app(app_id: uuid.UUID, user_id: str) -> None:
        """
        删除应用

        :param app_id: 应用唯一标识
        :param user_id: 用户唯一标识
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)
            if app_obj.authorId != user_id:
                msg = f"[AppCenterManager] 权限不足: {user_id} -> {app_obj.authorId}"
                raise InstancePermissionError(msg)
            await session.delete(app_obj)
            await session.commit()


    @staticmethod
    async def get_recently_used_apps(count: int, user_id: str) -> RecentAppList:
        """
        获取用户最近使用的应用列表

        :param count: 应用数量
        :param user_id: 用户唯一标识
        :return: 最近使用的应用列表
        """
        async with postgres.session() as session:
            recent_apps = list((await session.scalars(
                select(UserAppUsage.appId).where(
                    UserAppUsage.userId == user_id,
                ).order_by(
                    UserAppUsage.lastUsed.desc(),
                ).limit(count),
            )).all())
            result = []
            for app_id in recent_apps:
                name = (await session.scalars(select(App.name).where(App.id == app_id))).one_or_none()
                if name:
                    result.append(RecentAppListItem(appId=app_id, name=name))

            return RecentAppList(applications=result)


    @staticmethod
    async def update_recent_app(user_id: str, app_id: uuid.UUID) -> None:
        """
        更新用户的最近使用应用列表

        :param user_id: 用户唯一标识
        :param app_id: 应用唯一标识
        :return: 更新是否成功
        """
        async with postgres.session() as session:
            app_usage = (await session.scalars(
                select(UserAppUsage).where(
                    and_(
                        UserAppUsage.userId == user_id,
                        UserAppUsage.appId == app_id,
                    ),
                ),
            )).one_or_none()

            if app_usage:
                # 存在则更新count和lastUsed
                app_usage.lastUsed = datetime.now(UTC)
                app_usage.usageCount += 1
                await session.merge(app_usage)
            else:
                # 不存在则创建新条目
                app_usage = UserAppUsage(
                    userId=user_id,
                    appId=app_id,
                    lastUsed=datetime.now(UTC),
                    usageCount=1,
                )
                session.add(app_usage)

            await session.commit()


    @staticmethod
    async def _get_app_data(app_id: uuid.UUID, user_id: str, *, check_author: bool = True) -> App:
        """
        从数据库获取应用数据并验证权限

        :param app_id: 应用唯一标识
        :param user_id: 用户唯一标识
        :param check_author: 是否检查作者
        :return: 应用数据
        """
        async with postgres.session() as session:
            app_data = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_data:
                msg = f"【AppCenterManager】应用不存在: {app_id}"
                raise ValueError(msg)
            if check_author and app_data.authorId != user_id:
                msg = f"【AppCenterManager】权限不足: {user_id} -> {app_data.authorId}"
                raise InstancePermissionError(msg)
            return app_data


    @staticmethod
    async def _create_flow_metadata(
        common_params: dict,
        data: AppData | None = None,
        app_data: FlowAppMetadata | None = None,
        *,
        published: bool | None = None,
    ) -> FlowAppMetadata:
        """创建工作流应用的元数据"""
        metadata = FlowAppMetadata(**common_params)

        if data:
            metadata.links = data.links
            metadata.first_questions = data.first_questions
        elif app_data:
            metadata.links = app_data.links
            metadata.first_questions = app_data.first_questions

        if app_data:
            metadata.flows = app_data.flows
        else:
            metadata.flows = []

        if app_data:
            if published is None:
                metadata.published = getattr(app_data, "published", False)
            else:
                metadata.published = published
        elif published is not None:
            metadata.published = published
        else:
            metadata.published = False

        return metadata


    @staticmethod
    async def _create_agent_metadata(
        common_params: dict,
        user_id: str,
        data: AppData | None = None,
        *,
        published: bool | None = None,
    ) -> AgentAppMetadata:
        """创建 Agent 应用的元数据"""
        metadata = AgentAppMetadata(**common_params)

        if data is not None and hasattr(data, "mcp_service") and data.mcp_service:
            activated_mcp_ids = []
            for svc in data.mcp_service:
                is_activated = await MCPServiceManager.is_active(user_id, svc)
                if is_activated:
                    activated_mcp_ids.append(svc)
            metadata.mcp_service = activated_mcp_ids
        else:
            metadata.mcp_service = []

        if published is not None:
            metadata.published = published
        else:
            metadata.published = False

        return metadata

    @staticmethod
    async def _create_metadata(  # noqa: PLR0913
        app_type: AppType,
        app_id: uuid.UUID,
        user_id: str,
        data: AppData | None = None,
        app_data: FlowAppMetadata | AgentAppMetadata | None = None,
        *,
        published: bool | None = None,
    ) -> FlowAppMetadata | AgentAppMetadata:
        """
        创建应用元数据

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_id: 用户唯一标识
        :param data: 应用数据，用于新建或更新时提供
        :param app_data: 现有应用数据，用于更新时提供
        :param published: 发布状态，用于更新时提供
        :return: 应用元数据
        :raises ValueError: 无效应用类型或缺少必要数据
        """
        source = data if data else app_data
        if not source:
            msg = "必须提供 data 或 app_data 参数"
            raise ValueError(msg)

        common_params = {
            "type": MetadataType.APP,
            "id": app_id,
            "author": user_id,
            "icon": source.icon,
            "name": source.name,
            "description": source.description,
            "history_len": data.history_len if data else APP_DEFAULT_HISTORY_LEN,
            "permission": Permission(
                type=data.permission.type,
                users=data.permission.users or [],
            ) if data else (app_data.permission if app_data else None),
        }

        if app_type == AppType.AGENT and isinstance(app_data, AgentAppMetadata):
            return await AppCenterManager._create_agent_metadata(
                common_params, user_id, data, published=published,
            )
        if app_type == AppType.FLOW and isinstance(app_data, FlowAppMetadata):
            return await AppCenterManager._create_flow_metadata(common_params, data, app_data, published=published)

        msg = "无效的应用类型或元数据类型"
        raise ValueError(msg)


    @staticmethod
    async def _process_app_and_save(
        app_type: AppType,
        app_id: uuid.UUID,
        user_id: str,
        data: AppData | None = None,
        *,
        published: bool | None = None,
    ) -> Any:
        """
        处理应用元数据创建和保存

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_id: 用户唯一标识
        :param data: 应用数据，用于新建或更新时提供
        :param published: 发布状态，用于更新时提供
        :return: 应用元数据
        """
        app_data = await pool.app_loader.read_metadata(app_id)
        metadata = await AppCenterManager._create_metadata(
            app_type=app_type,
            app_id=app_id,
            user_id=user_id,
            data=data,
            app_data=app_data,
            published=published,
        )

        await pool.app_loader.save(metadata, app_id)
        return metadata
