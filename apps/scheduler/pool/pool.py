"""资源池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
from typing import Optional

import ray
from anyio import Path

from apps.common.config import config
from apps.constants import LOGGER, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.entities.flow_topology import FlowItem
from apps.models.mongo import MongoDB
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader import CallLoader, ServiceLoader


@ray.remote
class Pool:
    """资源池"""

    async def init(self) -> None:
        """加载全部文件系统内的资源"""
        # 加载Call
        await CallLoader().load()

        # 检查文件变动
        checker = FileChecker()
        changed_service, deleted_service = await checker.diff(MetadataType.SERVICE)

        # 处理Service
        service_loader = ServiceLoader.remote()

        # 批量删除
        delete_task = [service_loader.delete.remote(service) for service in changed_service]  # type: ignore[attr-type]
        delete_task += [service_loader.delete.remote(service) for service in deleted_service]  # type: ignore[attr-type]
        await asyncio.gather(*delete_task)

        # 批量加载
        load_task = [service_loader.load.remote(service, checker.hashes[Path(SERVICE_DIR + "/" + service).as_posix()]) for service in changed_service]  # type: ignore[attr-type]
        await asyncio.gather(*load_task)

        # 完成Service load
        ray.kill(service_loader)

        # 加载App
        changed_app, deleted_app = await checker.diff(MetadataType.APP)


    async def save(self, *, is_deletion: bool = False) -> None:
        """保存【单个】资源"""
        pass


    async def get_flow_metadata(self, app_id: str) -> Optional[FlowItem]:
        """从数据库中获取特定App的全部Flow的元数据"""
        app_collection = MongoDB.get_collection("app")
        try:
            flow_list = await app_collection.find_one({"_id": app_id}, {"flows": 1})
        except Exception as e:
            err = f"获取App{app_id}的Flow列表失败：{e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        if not flow_list:
            return None


    async def get_flow(self, app_id: str, flow_id: str) -> Optional[FlowItem]:
        """从数据库中获取单个Flow的全部数据"""
        pass
