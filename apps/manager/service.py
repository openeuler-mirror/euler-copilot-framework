"""语义接口中心 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import uuid
from typing import Any, Optional

from jsonschema import ValidationError, validate

from apps.constants import LOGGER
from apps.entities.enum_var import SearchType
from apps.entities.pool import NodePool, ServicePool
from apps.entities.response_data import ServiceApiData, ServiceCardItem
from apps.models.mongo import MongoDB
from apps.scheduler.openapi import reduce_openapi_spec


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
        services = [
            ServiceCardItem(
                serviceId=service_pool.id,
                icon="",
                name=service_pool.name,
                description=service_pool.description,
                author=service_pool.author,
                favorited=(user_sub in service_pool.favorites),
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
        services = [
            ServiceCardItem(
                serviceId=service_pool.id,
                icon="",
                name=service_pool.name,
                description=service_pool.description,
                author=service_pool.author,
                favorited=(user_sub in service_pool.favorites),
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
        # 更新 Node 信息
        node_collection = MongoDB.get_collection("node")
        await node_collection.delete_many({"service_id": service_id})
        openapi_spec_data = reduce_openapi_spec(data)
        for endpoint in openapi_spec_data.endpoints:
            await node_collection.insert_one(
                NodePool(
                    _id=str(uuid.uuid4()),
                    service_id=service_id,
                    name=endpoint.name,
                    api_path=f"{endpoint.method} {endpoint.uri}",
                    description=endpoint.description,
                    call_id="api",
                ).model_dump(),
            )
        yaml_hash = "hash"  # TODO: 计算 OpenAPI YAML 文件的哈希值
        # 存入数据库
        service_pool = ServicePool(
            _id=service_id,
            author=user_sub,
            name=data["info"]["title"],
            description=data["info"]["description"],
            openapi_hash=yaml_hash,
            openapi_spec=data,
        )
        service_collection = MongoDB.get_collection("service")
        await service_collection.insert_one(service_pool.model_dump())
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
        # 更新 Node 信息
        node_collection = MongoDB.get_collection("node")
        await node_collection.delete_many({"service_id": service_id})
        openapi_spec_data = reduce_openapi_spec(data)
        for endpoint in openapi_spec_data.endpoints:
            await node_collection.insert_one(
                NodePool(
                    _id=str(uuid.uuid4()),
                    service_id=service_id,
                    name=endpoint.name,
                    api_path=f"{endpoint.method} {endpoint.uri}",
                    description=endpoint.description,
                    call_id="api",
                ).model_dump(),
            )
        yaml_hash = "hash"  # TODO: 计算 OpenAPI YAML 文件的哈希值
        # 更新数据库
        service_pool = ServicePool(
            _id=service_id,
            author=user_sub,
            name=data["info"]["title"],
            description=data["info"]["description"],
            openapi_hash=yaml_hash,
            openapi_spec=data,
        )
        await service_collection.update_one(
            {"_id": service_id},
            {"$set": service_pool.model_dump()},
        )
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
        api_list = []
        for db_node in db_nodes:
            node = NodePool.model_validate(db_node)
            api_list.extend(
                ServiceApiData(
                    name=node.name,
                    path=node.api_path or "",
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
        return service_pool_store.name, service_pool_store.openapi_spec

    @staticmethod
    async def delete_service(
        user_sub: str,
        service_id: str,
    ) -> bool:
        """删除服务"""
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
        # 删除服务
        await service_collection.delete_one({"_id": service_id})
        # 删除 Node 信息
        node_collection = MongoDB.get_collection("node")
        await node_collection.delete_many({"service_id": service_id})
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
        db_service = await service_collection.find_one({"_id": service_id})
        if not db_service:
            msg = "Service not found"
            raise ValueError(msg)
        service_pool_store = ServicePool.model_validate(db_service)
        already_favorited = user_sub in service_pool_store.favorites
        if already_favorited == favorited:
            return False
        if favorited:
            service_pool_store.favorites.append(user_sub)
            service_pool_store.favorites = list(set(service_pool_store.favorites))
        else:
            service_pool_store.favorites.remove(user_sub)
        await service_collection.update_one(
            {"_id": service_id},
            {"$set": service_pool_store.model_dump()},
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
        service_collection = MongoDB.get_collection("service")
        cursor = service_collection.find({"favorites": {"$in": [user_sub]}})
        return [ServicePool.model_validate(doc).id async for doc in cursor]

    @staticmethod
    def _validate_service_data(data: dict[str, Any]) -> bool:
        """验证服务数据"""
        # 验证数据是否为空
        if not data:
            msg = "Service data is empty"
            raise ValueError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        openapi_schema = {
            "type": "object",
            "properties": {
                "openapi": {"type": "string"},
                "info": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "version": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["title", "version", "description"],
                },
                "paths": {"type": "object"},
            },
            "required": ["openapi", "info", "paths"],
        }
        try:
            validate(instance=data, schema=openapi_schema)
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
