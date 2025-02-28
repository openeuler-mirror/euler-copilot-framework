"""画像领域管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from apps.entities.collection import Domain
from apps.entities.request_data import PostDomainData
from apps.models.mongo import MongoDB

logger = logging.getLogger("ray")


class DomainManager:
    """用户画像相关操作"""

    @staticmethod
    async def get_domain() -> list[Domain]:
        """获取所有领域信息

        :return: 领域信息列表
        """
        try:
            domain_collection = MongoDB.get_collection("domain")
            return [Domain(**domain) async for domain in domain_collection.find()]
        except Exception:
            logger.exception("[DomainManager] 获取领域失败")
            return []

    @staticmethod
    async def get_domain_by_domain_name(domain_name: str) -> Optional[Domain]:
        """根据领域名称获取领域信息

        :param domain_name: 领域名称
        :return: 领域信息
        """
        try:
            domain_collection = MongoDB.get_collection("domain")
            domain_data = await domain_collection.find_one({"domain_name": domain_name})
            if domain_data:
                return Domain(**domain_data)
            return None
        except Exception:
            logger.exception("[DomainManager] 通过领域名称获取领域失败")
            return None

    @staticmethod
    async def add_domain(domain_data: PostDomainData) -> bool:
        """添加领域

        :param domain_data: 领域信息
        :return: 是否添加成功
        """
        try:
            domain = Domain(
                name=domain_data.domain_name,
                definition=domain_data.domain_description,
            )
            domain_collection = MongoDB.get_collection("domain")
            await domain_collection.insert_one(domain.model_dump(by_alias=True))
            return True
        except Exception:
            logger.exception("[DomainManager] 添加领域失败")
            return False

    @staticmethod
    async def update_domain_by_domain_name(domain_data: PostDomainData) -> Optional[Domain]:
        """更新领域

        :param domain_data: 领域信息
        :return: 更新后的领域信息
        """
        try:
            update_dict = {
                "definition": domain_data.domain_description,
                "updated_at": round(datetime.now(tz=timezone.utc).timestamp(), 3),
            }
            domain_collection = MongoDB.get_collection("domain")
            await domain_collection.update_one(
                {"name": domain_data.domain_name},
                {"$set": update_dict},
            )
            return Domain(name=domain_data.domain_name, **update_dict)
        except Exception:
            logger.exception("[DomainManager] 更新领域失败")
            return None

    @staticmethod
    async def delete_domain_by_domain_name(domain_data: PostDomainData) -> bool:
        """删除领域

        :param domain_data: 领域信息
        :return: 删除成功返回True，否则返回False
        """
        try:
            domain_collection = MongoDB.get_collection("domain")
            await domain_collection.delete_one({"name": domain_data.domain_name})
            return True
        except Exception:
            logger.exception("[DomainManager] 通过领域名称删除领域失败")
            return False
