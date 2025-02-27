"""资源池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import importlib
import logging
from typing import Any, Optional

import ray
from anyio import Path

from apps.constants import APP_DIR, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.entities.flow import Flow
from apps.entities.pool import AppFlow
from apps.models.mongo import MongoDB
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader import (
    AppLoader,
    CallLoader,
    FlowLoader,
    ServiceLoader,
)

logger = logging.getLogger(__name__)


@ray.remote
class Pool:
    """资源池"""

    async def init(self) -> None:
        """加载全部文件系统内的资源"""
        # 加载Call
        logger.info("[Pool] 载入Call")
        await CallLoader().load()

        # 检查文件变动
        logger.info("[Pool] 检查文件变动")
        checker = FileChecker()
        changed_service, deleted_service = await checker.diff(MetadataType.SERVICE)

        # 处理Service
        logger.info("[Pool] 载入Service")
        service_loader = ServiceLoader()

        # 批量删除
        for service in changed_service:
            await service_loader.delete(service)
        for service in deleted_service:
            await service_loader.delete(service)

        # 批量加载
        for service in changed_service:
            hash_key = Path(SERVICE_DIR + "/" + service).as_posix()
            if hash_key in checker.hashes:
                await service_loader.load(service, checker.hashes[hash_key])

        # 加载App
        logger.info("[Pool] 载入App")
        changed_app, deleted_app = await checker.diff(MetadataType.APP)
        app_loader = AppLoader()

        # 批量删除App
        for app in changed_app:
            await app_loader.delete(app)
        for app in deleted_app:
            await app_loader.delete(app)

        # 批量加载App
        for app in changed_app:
            hash_key = Path(APP_DIR + "/" + app).as_posix()
            if hash_key in checker.hashes:
                await app_loader.load(app, checker.hashes[hash_key])


    async def save(self, *, is_deletion: bool = False) -> None:
        """保存【单个】资源"""
        pass


    async def get_flow_metadata(self, app_id: str) -> list[AppFlow]:
        """从数据库中获取特定App的全部Flow的元数据"""
        app_collection = MongoDB.get_collection("app")
        flow_metadata_list = []
        try:
            flow_list = await app_collection.find_one({"_id": app_id}, {"flows": 1})
            if not flow_list:
                return []
            for flow in flow_list["flows"]:
                flow_metadata_list += [AppFlow.model_validate(flow)]
            return flow_metadata_list
        except Exception:
            logger.exception("[Pool] 获取App %s 的Flow列表失败", app_id)
            return []


    async def get_flow(self, app_id: str, flow_id: str) -> Optional[Flow]:
        """从文件系统中获取单个Flow的全部数据"""
        logger.info("[Pool] 获取工作流 %s", flow_id)
        flow_loader = FlowLoader()
        return await flow_loader.load(app_id, flow_id)


    async def get_call(self, call_path: str) -> Any:
        """拿到Call的信息"""
        call_path_split = call_path.split("::")
        if not call_path_split:
            err = f"[Pool] Call路径{call_path}不合法"
            logger.error(err)
            raise ValueError(err)

        # Python类型的Call
        if call_path_split[0] == "python":
            try:
                call_module = importlib.import_module(call_path_split[1])
                return getattr(call_module, call_path_split[2])
            except Exception as e:
                err = f"[Pool] 获取Call{call_path}类失败"
                logger.exception(err)
                raise RuntimeError(err) from e
        return None
