# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""画像领域管理"""

import logging
from datetime import UTC, datetime

from apps.common.mongo import MongoDB
from apps.schemas.collection import Domain
from apps.schemas.request_data import PostDomainData

logger = logging.getLogger(__name__)


class DomainManager:
    """用户画像相关操作"""

    @staticmethod
    async def get_domain() -> list[Domain]:
        """
        获取所有领域信息

        :return: 领域信息列表
        """
        domain_collection = MongoDB.get_collection("domain")
        return [Domain(**domain) async for domain in domain_collection.find()]

    @staticmethod
    async def get_domain_by_domain_name(domain_name: str) -> Domain | None:
        """
        根据领域名称获取领域信息

        :param domain_name: 领域名称
        :return: 领域信息
        """
        domain_collection = MongoDB.get_collection("domain")
        domain_data = await domain_collection.find_one({"domain_name": domain_name})
        if domain_data:
            return Domain(**domain_data)
        return None

    @staticmethod
    async def add_domain(domain_data: PostDomainData) -> None:
        """
        添加领域

        :param domain_data: 领域信息
        """
        domain = Domain(
            name=domain_data.domain_name,
            definition=domain_data.domain_description,
        )
        domain_collection = MongoDB.get_collection("domain")
        await domain_collection.insert_one(domain.model_dump(by_alias=True))

    @staticmethod
    async def update_domain_by_domain_name(domain_data: PostDomainData) -> Domain:
        """
        更新领域

        :param domain_data: 领域信息
        :return: 更新后的领域信息
        """
        update_dict = {
            "definition": domain_data.domain_description,
            "updated_at": round(datetime.now(tz=UTC).timestamp(), 3),
        }
        domain_collection = MongoDB.get_collection("domain")
        await domain_collection.update_one(
            {"name": domain_data.domain_name},
            {"$set": update_dict},
        )
        return Domain(name=domain_data.domain_name, **update_dict)

    @staticmethod
    async def delete_domain_by_domain_name(domain_data: PostDomainData) -> None:
        """
        删除领域

        :param domain_data: 领域信息
        """
        domain_collection = MongoDB.get_collection("domain")
        await domain_collection.delete_one({"name": domain_data.domain_name})
