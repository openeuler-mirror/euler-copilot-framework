# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""语义接口中心 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import yaml
from anyio import Path
from sqlalchemy import Select, and_, delete, func, or_, select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models import (
    NodeInfo,
    PermissionType,
    Service,
    ServiceACL,
    User,
    UserFavorite,
    UserFavoriteType,
)
from apps.scheduler.openapi import ReducedOpenAPISpec
from apps.scheduler.pool.loader.openapi import OpenAPILoader
from apps.scheduler.pool.loader.service import ServiceLoader
from apps.schemas.enum_var import SearchType
from apps.schemas.flow import (
    Permission,
    ServiceApiConfig,
    ServiceMetadata,
)
from apps.schemas.service import ServiceApiData, ServiceCardItem

logger = logging.getLogger(__name__)


class ServiceCenterManager:
    """语义接口中心管理器"""

    @staticmethod
    async def _build_service_query(
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
        base_conditions: list | None = None,
    ) -> tuple[Select[tuple[Service, ...]], Select[tuple[int]]]:
        """
        构建服务查询语句(包含数据查询和总数查询)

        :param search_type: 搜索类型
        :param keyword: 搜索关键字
        :param page: 页码
        :param page_size: 页面大小
        :param base_conditions: 额外的基础条件
        :return: (数据查询语句, 总数查询语句)
        """
        # 构建搜索条件
        search_conditions = []
        if keyword:
            search_condition_map = {
                SearchType.ALL: or_(
                    Service.name.like(f"%{keyword}%"),
                    Service.description.like(f"%{keyword}%"),
                    Service.authorId.like(f"%{keyword}%"),
                ),
                SearchType.NAME: Service.name.like(f"%{keyword}%"),
                SearchType.DESCRIPTION: Service.description.like(f"%{keyword}%"),
                SearchType.AUTHOR: Service.authorId.like(f"%{keyword}%"),
            }
            search_conditions = [search_condition_map.get(search_type)]

        all_conditions = (base_conditions or []) + search_conditions

        base_query = select(Service)
        if all_conditions:
            base_query = base_query.where(and_(*all_conditions))

        data_query = base_query.order_by(Service.updatedAt.desc()).offset((page - 1) * page_size).limit(page_size)
        count_query = select(func.count()).select_from(base_query.subquery())

        return data_query, count_query


    @staticmethod
    async def fetch_all_services(
        user_id: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取所有服务列表"""
        async with postgres.session() as session:
            data_query, count_query = await ServiceCenterManager._build_service_query(
                search_type, keyword, page, page_size,
            )
            service_pools = list((await session.scalars(data_query)).all())
            total_count = (await session.scalar(count_query)) or 0

        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_id)
        services = [
            ServiceCardItem(
                serviceId=service_pool.id,
                icon="",
                name=service_pool.name,
                description=service_pool.description,
                author=service_pool.author,
                favorited=(service_pool.id in fav_service_ids),
            )
            for service_pool in service_pools
        ]
        return services, total_count


    @staticmethod
    async def fetch_user_services(
        user_id: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户创建的服务"""
        if search_type == SearchType.AUTHOR:
            if keyword is not None and user_id not in keyword:
                return [], 0
            keyword = user_id

        async with postgres.session() as session:
            data_query, count_query = await ServiceCenterManager._build_service_query(
                search_type, keyword, page, page_size, base_conditions=[Service.authorId == user_id],
            )
            service_pools = list((await session.scalars(data_query)).all())
            total_count = (await session.scalar(count_query)) or 0

        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_id)
        services = [
            ServiceCardItem(
                serviceId=service_pool.id,
                icon="",
                name=service_pool.name,
                description=service_pool.description,
                author=service_pool.author,
                favorited=(service_pool.id in fav_service_ids),
            )
            for service_pool in service_pools
        ]
        return services, total_count


    @staticmethod
    async def fetch_favorite_services(
        user_id: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户收藏的服务(使用CTE优化查询)"""
        async with postgres.session() as session:
            # 使用CTE获取用户收藏的服务ID
            favorite_cte = (
                select(UserFavorite.itemId)
                .where(
                    and_(
                        UserFavorite.userId == user_id,
                        UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                    ),
                )
                .cte("user_favorites")
            )

            # 使用统一的查询构建方法,添加收藏条件
            data_query, count_query = await ServiceCenterManager._build_service_query(
                search_type, keyword, page, page_size,
                base_conditions=[Service.id.in_(select(favorite_cte.c.itemId))],
            )

            service_pools = list((await session.scalars(data_query)).all())
            total_count = (await session.scalar(count_query)) or 0

            services = [
                ServiceCardItem(
                    serviceId=service_pool.id,
                    icon="",
                    name=service_pool.name,
                    description=service_pool.description,
                    author=service_pool.author,
                    favorited=True,
                )
                for service_pool in service_pools
            ]
            return services, total_count


    @staticmethod
    async def create_service(
        user_id: str,
        data: dict[str, Any],
    ) -> uuid.UUID:
        """创建服务"""
        service_id = uuid.uuid4()
        # 校验 OpenAPI 规范的 JSON Schema
        validated_data = await ServiceCenterManager._validate_service_data(data)

        # 检查是否存在相同服务
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    and_(
                        Service.name == validated_data.id,
                        Service.description == validated_data.description,
                    ),
                ),
            )).one_or_none()

            if db_service:
                msg = "[ServiceCenterManager] 已存在相同名称和描述的服务"
                raise RuntimeError(msg)

        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=validated_data.id,
            description=validated_data.description,
            author=user_id,
            api=ServiceApiConfig(server=validated_data.servers),
            permission=Permission(type=PermissionType.PUBLIC),  # 默认公开
        )
        service_loader = ServiceLoader()
        await service_loader.save(service_id, service_metadata, data)
        # 返回服务ID
        return service_id


    @staticmethod
    async def update_service(
        user_id: str,
        service_id: uuid.UUID,
        data: dict[str, Any],
    ) -> uuid.UUID:
        """更新服务"""
        # 验证用户权限
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    Service.id == service_id,
                ),
            )).one_or_none()
            if not db_service:
                msg = "[ServiceCenterManager] Service not found"
                raise RuntimeError(msg)
            if db_service.authorId != user_id:
                msg = "[ServiceCenterManager] Permission denied"
                raise RuntimeError(msg)
            db_service.updatedAt = datetime.now(tz=UTC)
        # 校验 OpenAPI 规范的 JSON Schema
        validated_data = await ServiceCenterManager._validate_service_data(data)
        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=validated_data.id,
            description=validated_data.description,
            author=user_id,
            api=ServiceApiConfig(server=validated_data.servers),
        )
        service_loader = ServiceLoader()
        await service_loader.save(service_id, service_metadata, data)
        # 返回服务ID
        return service_id


    @staticmethod
    async def get_service_apis(
        service_id: uuid.UUID,
    ) -> tuple[str, list[ServiceApiData]]:
        """获取服务API列表"""
        # 获取服务名称
        async with postgres.session() as session:
            service_name = (await session.scalars(
                select(Service.name).where(
                    Service.id == service_id,
                ),
            )).one_or_none()
            if not service_name:
                msg = "[ServiceCenterManager] Service not found"
                raise RuntimeError(msg)

            # 根据 service_id 获取 API 列表
            node_data = (await session.scalars(
                select(NodeInfo).where(
                    NodeInfo.serviceId == service_id,
                ),
            )).all()
            api_list = [
                ServiceApiData(
                    name=node.name,
                    path=f"{node.knownParams['method'].upper()} {node.knownParams['url']}"
                    if node.knownParams and "method" in node.knownParams and "url" in node.knownParams
                    else "",
                    description=node.description,
                )
                for node in node_data
            ]
            return service_name, api_list


    @staticmethod
    async def get_service_data(
        user_id: str,
        service_id: uuid.UUID,
    ) -> tuple[str, dict[str, Any]]:
        """获取服务数据"""
        # 验证用户权限
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    and_(
                        Service.id == service_id,
                        Service.authorId == user_id,
                    ),
                ),
            )).one_or_none()

            if not db_service:
                msg = "[ServiceCenterManager] Service not found or permission denied"
                raise RuntimeError(msg)

        service_path = (
            Path(config.deploy.data_dir) / "semantics" / "service" / str(service_id) / "openapi" / "api.yaml"
        )
        async with await service_path.open() as f:
            service_data = yaml.safe_load(await f.read())
        return db_service.name, service_data


    @staticmethod
    async def get_service_metadata(
        user_id: str,
        service_id: uuid.UUID,
    ) -> ServiceMetadata:
        """获取服务元数据"""
        async with postgres.session() as session:
            allowed_user = list((await session.scalars(
                select(ServiceACL.userId).where(
                    ServiceACL.serviceId == service_id,
                ),
            )).all())
            if user_id in allowed_user:
                db_service = (await session.scalars(
                    select(Service).where(
                        and_(
                            Service.id == service_id,
                            Service.permission == PermissionType.PRIVATE,
                        ),
                    ),
                )).one_or_none()
            else:
                db_service = (await session.scalars(
                    select(Service).where(
                        and_(
                            Service.id == service_id,
                            or_(
                                and_(
                                    Service.authorId == user_id,
                                    Service.permission == PermissionType.PRIVATE,
                                ),
                                Service.permission == PermissionType.PUBLIC,
                                Service.authorId == user_id,
                            ),
                        ),
                    ),
                )).one_or_none()
            if not db_service:
                msg = "[ServiceCenterManager] Service not found or permission denied"
                raise RuntimeError(msg)

        metadata_path = (
            Path(config.deploy.data_dir) / "semantics" / "service" / str(service_id) / "metadata.yaml"
        )
        async with await metadata_path.open() as f:
            metadata_data = yaml.safe_load(await f.read())
        return ServiceMetadata.model_validate(metadata_data)


    @staticmethod
    async def delete_service(user_id: str, service_id: uuid.UUID) -> None:
        """删除服务"""
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    and_(
                        Service.id == service_id,
                        Service.authorId == user_id,
                    ),
                ),
            )).one_or_none()
            if not db_service:
                msg = "[ServiceCenterManager] Service not found or permission denied"
                raise RuntimeError(msg)

            # 删除服务
            service_loader = ServiceLoader()
            await service_loader.delete(service_id)
            # 删除ACL
            await session.execute(
                delete(ServiceACL).where(
                    ServiceACL.serviceId == service_id,
                ),
            )
            # 删除收藏
            await session.execute(
                delete(UserFavorite).where(
                    UserFavorite.itemId == service_id,
                    UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                ),
            )
            await session.commit()


    @staticmethod
    async def modify_favorite_service(
        user_id: str,
        service_id: uuid.UUID,
        *,
        favorited: bool,
    ) -> None:
        """修改收藏状态"""
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(func.count(Service.id)).where(
                    Service.id == service_id,
                ),
            )).one()
            if not db_service:
                msg = f"[ServiceCenterManager] Service未找到: {service_id}"
                logger.warning(msg)
                raise RuntimeError(msg)

            user = (await session.scalars(
                select(func.count(User.id)).where(
                    User.id == user_id,
                ),
            )).one()
            if not user:
                msg = f"[ServiceCenterManager] 用户未找到: {user_id}"
                logger.warning(msg)
                raise RuntimeError(msg)

            # 检查是否已收藏
            user_favourite = (await session.scalars(
                select(UserFavorite).where(
                    and_(
                        UserFavorite.itemId == service_id,
                        UserFavorite.userId == user_id,
                        UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                    ),
                ),
            )).one_or_none()
            if not user_favourite and favorited:
                # 创建收藏条目
                user_favourite = UserFavorite(
                    itemId=service_id,
                    userId=user_id,
                    favouriteType=UserFavoriteType.SERVICE,
                )
                session.add(user_favourite)
                await session.commit()
            elif user_favourite and not favorited:
                # 删除收藏条目
                await session.delete(user_favourite)
                await session.commit()


    @staticmethod
    async def _get_favorite_service_ids_by_user(user_id: str) -> list[uuid.UUID]:
        """获取用户收藏的服务ID"""
        async with postgres.session() as session:
            user_favourite = (await session.scalars(
                select(UserFavorite).where(
                    UserFavorite.userId == user_id,
                    UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                ),
            )).all()
            return [user_favourite.itemId for user_favourite in user_favourite]


    @staticmethod
    async def _validate_service_data(data: dict[str, Any]) -> ReducedOpenAPISpec:
        """验证服务数据"""
        # 验证数据是否为空
        if not data:
            msg = "[ServiceCenterManager] 服务数据为空"
            raise ValueError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        return await OpenAPILoader().load_dict(data)
