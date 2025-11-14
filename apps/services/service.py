# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""语义接口中心 Manager"""

import logging
import uuid
from typing import Any

import yaml
from anyio import Path

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.exceptions import InstancePermissionError, ServiceIDError
from apps.scheduler.openapi import ReducedOpenAPISpec
from apps.scheduler.pool.loader.openapi import OpenAPILoader
from apps.scheduler.pool.loader.service import ServiceLoader
from apps.schemas.collection import User
from apps.schemas.enum_var import SearchType
from apps.schemas.flow import (
    Permission,
    PermissionType,
    ServiceApiConfig,
    ServiceMetadata,
)
from apps.schemas.pool import NodePool, ServicePool
from apps.schemas.response_data import ServiceApiData, ServiceCardItem

logger = logging.getLogger(__name__)


class ServiceCenterManager:
    """语义接口中心管理器"""

    @staticmethod
    async def fetch_all_services(
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取所有服务列表"""
        filters = ServiceCenterManager._build_filters({}, search_type, keyword) if keyword else {}
        service_pools, total_count = await ServiceCenterManager._search_service(filters, page, page_size)
        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_sub)
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
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户创建的服务"""
        if search_type == SearchType.AUTHOR:
            if keyword is not None and keyword not in user_sub:
                return [], 0
            keyword = user_sub
        base_filter = {"author": user_sub}
        filters = ServiceCenterManager._build_filters(base_filter, search_type, keyword) if keyword else base_filter
        service_pools, total_count = await ServiceCenterManager._search_service(filters, page, page_size)
        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_sub)
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
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户收藏的服务"""
        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_sub)
        base_filter = {"_id": {"$in": fav_service_ids}}
        filters = ServiceCenterManager._build_filters(base_filter, search_type, keyword) if keyword else base_filter
        service_pools, total_count = await ServiceCenterManager._search_service(filters, page, page_size)
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
        user_sub: str,
        data: dict[str, Any],
    ) -> str:
        """创建服务"""
        service_id = str(uuid.uuid4())
        # 校验 OpenAPI 规范的 JSON Schema
        validated_data = await ServiceCenterManager._validate_service_data(data)
        # 检查是否存在相同服务
        service_collection = MongoDB.get_collection("service")
        db_service = await service_collection.find_one(
            {
                "name": validated_data.id,
                "description": validated_data.description,
            },
        )
        if db_service:
            msg = "[ServiceCenterManager] 已存在相同名称和描述的服务"
            raise ServiceIDError(msg)
        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=validated_data.id,
            description=validated_data.description,
            version=validated_data.version,
            author=user_sub,
            api=ServiceApiConfig(server=validated_data.servers),
            permission=Permission(type=PermissionType.PUBLIC),  # 默认公开
        )
        service_loader = ServiceLoader()
        await service_loader.save(service_id, service_metadata, data)
        # 返回服务ID
        return service_id

    @staticmethod
    async def update_service(
        user_sub: str,
        service_id: str,
        data: dict[str, Any],
    ) -> str:
        """更新服务"""
        # 验证用户权限
        service_collection = MongoDB.get_collection("service")
        db_service = await service_collection.find_one({"_id": service_id})
        if not db_service:
            msg = "Service not found"
            raise ServiceIDError(msg)
        service_pool_store = ServicePool.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise InstancePermissionError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        validated_data = await ServiceCenterManager._validate_service_data(data)
        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=validated_data.id,
            description=validated_data.description,
            version=validated_data.version,
            author=user_sub,
            api=ServiceApiConfig(server=validated_data.servers),
        )
        service_loader = ServiceLoader()
        await service_loader.save(service_id, service_metadata, data)
        # 返回服务ID
        return service_id

    @staticmethod
    async def get_service_apis(
        service_id: str,
    ) -> tuple[str, list[ServiceApiData]]:
        """获取服务API列表"""
        # 获取服务名称
        service_collection = MongoDB.get_collection("service")
        db_service = await service_collection.find_one({"_id": service_id})
        if not db_service:
            msg = "Service not found"
            raise ServiceIDError(msg)
        service_pool_store = ServicePool.model_validate(db_service)
        # 根据 service_id 获取 API 列表
        node_collection = MongoDB.get_collection("node")
        db_nodes = await node_collection.find({"service_id": service_id}).to_list()
        api_list: list[ServiceApiData] = []
        for db_node in db_nodes:
            node = NodePool.model_validate(db_node)
            api_list.append(
                ServiceApiData(
                    name=node.name,
                    path=f"{node.known_params['method'].upper()} {node.known_params['url']}"
                    if node.known_params and "method" in node.known_params and "url" in node.known_params
                    else "",
                    description=node.description,
                ),
            )
        return service_pool_store.name, api_list

    @staticmethod
    async def get_service_data(
        user_sub: str,
        service_id: str,
    ) -> tuple[str, dict[str, Any]]:
        """获取服务数据"""
        # 验证用户权限
        service_collection = MongoDB.get_collection("service")
        match_conditions = [
            {"author": user_sub},
            {"permission.type": PermissionType.PUBLIC.value},
            {
                "$and": [
                    {"permission.type": PermissionType.PROTECTED.value},
                    {"permission.users": user_sub},
                ],
            },
        ]
        query = {"$and": [{"_id": service_id}, {"$or": match_conditions}]}
        db_service = await service_collection.find_one(query)
        if not db_service:
            msg = "Service not found"
            raise ServiceIDError(msg)
        service_pool_store = ServicePool.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise InstancePermissionError(msg)
        service_path = (
            Path(Config().get_config().deploy.data_dir) / "semantics" / "service" / service_id / "openapi" / "api.yaml"
        )
        async with await service_path.open() as f:
            service_data = yaml.safe_load(await f.read())
        return service_pool_store.name, service_data

    @staticmethod
    async def get_service_metadata(
        user_sub: str,
        service_id: str,
    ) -> ServiceMetadata:
        """获取服务元数据"""
        service_collection = MongoDB.get_collection("service")
        match_conditions = [
            {"author": user_sub},
            {"permission.type": PermissionType.PUBLIC.value},
            {
                "$and": [
                    {"permission.type": PermissionType.PROTECTED.value},
                    {"permission.users": user_sub},
                ],
            },
        ]
        query = {"$and": [{"_id": service_id}, {"$or": match_conditions}]}
        db_service = await service_collection.find_one(query)
        if not db_service:
            msg = "Service not found"
            raise ServiceIDError(msg)

        metadata_path = (
            Path(Config().get_config().deploy.data_dir) / "semantics" / "service" / service_id / "metadata.yaml"
        )
        async with await metadata_path.open() as f:
            metadata_data = yaml.safe_load(await f.read())
        return ServiceMetadata.model_validate(metadata_data)

    @staticmethod
    async def delete_service(
        user_sub: str,
        service_id: str,
    ) -> bool:
        """删除服务"""
        service_collection = MongoDB.get_collection("service")
        user_collection = MongoDB.get_collection("user")
        db_service = await service_collection.find_one({"_id": service_id})
        if not db_service:
            msg = "[ServiceCenterManager] Service未找到"
            raise ServiceIDError(msg)
        # 验证用户权限
        service_pool_store = ServicePool.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise InstancePermissionError(msg)
        # 删除服务
        service_loader = ServiceLoader()
        await service_loader.delete(service_id)
        # 删除用户收藏
        await user_collection.update_many(
            {"fav_services": {"$in": [service_id]}},
            {"$pull": {"fav_services": service_id}},
        )
        return True

    @staticmethod
    async def modify_favorite_service(
        user_sub: str,
        service_id: str,
        *,
        favorited: bool,
    ) -> bool:
        """修改收藏状态"""
        service_collection = MongoDB.get_collection("service")
        user_collection = MongoDB.get_collection("user")
        db_service = await service_collection.find_one({"_id": service_id})
        if not db_service:
            msg = f"[ServiceCenterManager] Service未找到: {service_id}"
            logger.warning(msg)
            raise ServiceIDError(msg)
        db_user = await user_collection.find_one({"_id": user_sub})
        if not db_user:
            msg = f"[ServiceCenterManager] 用户未找到: {user_sub}"
            logger.warning(msg)
            raise ServiceIDError(msg)
        user_data = User.model_validate(db_user)
        already_favorited = service_id in user_data.fav_services
        if already_favorited == favorited:
            return False
        if favorited:
            await user_collection.update_one(
                {"_id": user_sub},
                {"$addToSet": {"fav_services": service_id}},
            )
        else:
            await user_collection.update_one(
                {"_id": user_sub},
                {"$pull": {"fav_services": service_id}},
            )
        return True

    @staticmethod
    async def _search_service(
        search_conditions: dict,
        page: int,
        page_size: int,
    ) -> tuple[list[ServicePool], int]:
        """基于输入条件获取服务数据"""
        service_collection = MongoDB.get_collection("service")
        # 获取服务总数
        total = await service_collection.count_documents(search_conditions)
        # 分页查询
        skip = (page - 1) * page_size
        db_services = await service_collection.find(search_conditions).skip(skip).limit(page_size).to_list()
        if not db_services and total > 0:
            logger.warning("[ServiceCenterManager] 没有找到符合条件的服务: %s", search_conditions)
            return [], -1
        service_pools = [ServicePool.model_validate(db_service) for db_service in db_services]
        return service_pools, total

    @staticmethod
    async def _get_favorite_service_ids_by_user(user_sub: str) -> list[str]:
        """获取用户收藏的服务ID"""
        user_collection = MongoDB.get_collection("user")
        user_doc = await user_collection.find_one({"_id": user_sub})
        if user_doc is None:
            # 用户不存在，返回空的收藏列表
            return []
        user_data = User.model_validate(user_doc)
        return user_data.fav_services

    @staticmethod
    async def _validate_service_data(data: dict[str, Any]) -> ReducedOpenAPISpec:
        """验证服务数据"""
        # 验证数据是否为空
        if not data:
            msg = "[ServiceCenterManager] 服务数据为空"
            raise ValueError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        return await OpenAPILoader().load_dict(data)

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
