"""资源池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
import importlib
from typing import Any, Optional

import ray
from anyio import Path

from apps.common.config import config
from apps.constants import APP_DIR, LOGGER, SERVICE_DIR
from apps.entities.enum_var import MetadataType
from apps.entities.flow_topology import FlowItem
from apps.models.mongo import MongoDB
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader import (
    AppLoader,
    CallLoader,
    ServiceLoader,
)


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
        load_task = []
        for service in changed_service:
            hash_key = Path(SERVICE_DIR + "/" + service).as_posix()
            if hash_key in checker.hashes:
                load_task.append(service_loader.load.remote(service, checker.hashes[hash_key])) # type: ignore[attr-type]
        await asyncio.gather(*load_task)

        # 完成Service load
        ray.kill(service_loader)

        # 加载App
        changed_app, deleted_app = await checker.diff(MetadataType.APP)
        app_loader = AppLoader.remote()

        # 批量删除App
        delete_task = [app_loader.delete.remote(app) for app in changed_app]  # type: ignore[attr-type]
        delete_task += [app_loader.delete.remote(app) for app in deleted_app]  # type: ignore[attr-type]
        await asyncio.gather(*delete_task)

        # 批量加载App
        load_task = []
        for app in changed_app:
            hash_key = Path(APP_DIR + "/" + app).as_posix()
            if hash_key in checker.hashes:
                load_task.append(app_loader.load.remote(app, checker.hashes[hash_key])) # type: ignore[attr-type]
        await asyncio.gather(*load_task)

        # 完成App load
        ray.kill(app_loader)


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


    async def get_call(self, call_path: str) -> Any:
        """拿到Call的信息"""
        call_path_split = call_path.split("::")
        if not call_path_split:
            err = f"Call路径{call_path}不合法"
            LOGGER.error(err)
            raise ValueError(err)

        if call_path_split[0] == "python":
            try:
                call_module = importlib.import_module(call_path_split[1])
                call_class = getattr(call_module, call_path_split[2])
                return call_class
            except Exception as e:
                err = f"导入Call{call_path}失败：{e}"
                LOGGER.error(err)
                raise RuntimeError(err) from e
        return None
