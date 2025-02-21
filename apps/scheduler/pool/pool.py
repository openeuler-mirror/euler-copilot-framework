"""资源池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import ray

from apps.entities.enum_var import MetadataType
from apps.entities.flow_topology import FlowItem
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader import CallLoader


@ray.remote
class Pool:
    """资源池"""

    async def init(self) -> None:
        """加载全部文件系统内的资源"""
        # 加载Call
        await CallLoader().load()

        # 加载Services
        checker = FileChecker()
        changed_service, deleted_service = await checker.diff(MetadataType.SERVICE)
        # 加载App
        changed_app, deleted_app = await checker.diff(MetadataType.APP)


    def save(self, *, is_deletion: bool = False) -> None:
        """保存【单个】资源"""
        pass


    def get_flow(self, app_id: str, flow_id: str) -> FlowItem:
        pass
