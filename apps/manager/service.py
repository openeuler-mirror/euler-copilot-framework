"""语义接口中心 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""
import uuid
from typing import Any, Optional

import ray
import yaml
from anyio import Path
from jsonschema import ValidationError

from apps.common.config import config
from apps.constants import LOGGER, SERVICE_DIR
from apps.entities.collection import User
from apps.entities.enum_var import SearchType
from apps.entities.file_type import OpenAPI
from apps.entities.flow import ServiceApiConfig, ServiceMetadata
from apps.entities.pool import NodePool, ServicePool
from apps.entities.response_data import ServiceApiData, ServiceCardItem
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.service import ServiceLoader


class ServiceCenterManager:
    """语义接口中心管理器"""

    @staticmethod
    async def fetch_all_services(
        user_sub: str,
        search_type: SearchType,
        keyword: Optional[str],
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
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户创建的服务"""
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
        keyword: Optional[str],
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
        ServiceCenterManager._validate_service_data(data)
        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=data["info"]["title"],
            description=data["info"]["description"],
            version=data["info"]["version"],
            author=user_sub,
            api=ServiceApiConfig(server=data["servers"][0]["url"]),
        )
        service_loader = ServiceLoader.remote()
        await service_loader.save.remote(service_id, service_metadata, data)  # type: ignore[attr-type]
        ray.kill(service_loader)
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
            raise ValueError(msg)
        service_pool_store = ServicePool.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise ValueError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        ServiceCenterManager._validate_service_data(data)
        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=data["info"]["title"],
            description=data["info"]["description"],
            version=data["info"]["version"],
            author=user_sub,
            api=ServiceApiConfig(server=data["servers"][0]["url"]),
        )
        service_loader = ServiceLoader.remote()
        await service_loader.save.remote(service_id, service_metadata, data)  # type: ignore[attr-type]
        ray.kill(service_loader)
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
            raise ValueError(msg)
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
                    path="test path",
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
        db_service = await service_collection.find_one({"_id": service_id})
        if not db_service:
            msg = "Service not found"
            raise ValueError(msg)
        service_pool_store = ServicePool.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise ValueError(msg)
        service_path = Path(config["SEMANTICS_DIR"]) / SERVICE_DIR / service_id / "openapi" / "api.yaml"
        async with await Path(service_path).open() as f:
            service_data = yaml.safe_load(await f.read())
        return service_pool_store.name, service_data

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
            msg = "Service not found"
            raise ValueError(msg)
        # 验证用户权限
        service_pool_store = ServicePool.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise ValueError(msg)
        # 删除服务
        service_loader = ServiceLoader.remote()
        await service_loader.delete.remote(service_id)  # type: ignore[attr-type]
        ray.kill(service_loader)
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
            msg = f"[ServiceCenterManager] Service not found: {service_id}"
            LOGGER.warning(msg)
            raise ValueError(msg)
        db_user = await user_collection.find_one({"_id": user_sub})
        if not db_user:
            msg = f"[ServiceCenterManager] User not found: {user_sub}"
            LOGGER.warning(msg)
            raise ValueError(msg)
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
            LOGGER.warning(f"[ServiceCenterManager] No services found for conditions: {search_conditions}")
            return [], -1
        service_pools = [ServicePool.model_validate(db_service) for db_service in db_services]
        return service_pools, total

    @staticmethod
    async def _get_favorite_service_ids_by_user(user_sub: str) -> list[str]:
        """获取用户收藏的服务ID"""
        user_collection = MongoDB.get_collection("user")
        user_data = User.model_validate(await user_collection.find_one({"_id": user_sub}))
        return user_data.fav_services

    @staticmethod
    def _validate_service_data(data: dict[str, Any]) -> bool:
        """验证服务数据"""
        # 验证数据是否为空
        if not data:
            msg = "Service data is empty"
            raise ValueError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        try:
            OpenAPI.model_validate(data)
        except ValidationError as e:
            msg = f"Data does not conform to OpenAPI standard: {e.message}"
            raise ValueError(msg) from e
        return True

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
