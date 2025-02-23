"""资源池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path
from typing import Optional

import ray

from apps.common.config import config
from apps.constants import LOGGER, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.entities.flow_topology import FlowItem
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
        LOGGER.info(f"11111, checker.hashes: {checker.hashes}, changed_service: {changed_service}, deleted_service: {deleted_service}")

        # 处理Service
        service_loader = ServiceLoader()
        for service in changed_service:
            # 重载变化的Service
            await service_loader.load(service, checker.hashes[Path(SERVICE_DIR + "/" + service).as_posix()])
        for service in deleted_service:
            # 删除消失的Service
            await service_loader.delete(service)

        # 加载App
        changed_app, deleted_app = await checker.diff(MetadataType.APP)


    def save(self, *, is_deletion: bool = False) -> None:
        """保存【单个】资源"""
        pass


    def get_flow_metadata(self, app_id: str) -> Optional[FlowItem]:
        """从数据库中获取全部Flow的元数据"""
        pass


    def get_flow(self, app_id: str, flow_id: str) -> Optional[FlowItem]:
        """从数据库中获取单个Flow的全部数据"""
        pass
