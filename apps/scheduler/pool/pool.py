# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""资源池，包含语义接口、应用等的载入和保存"""

import logging
import sys
import uuid
from typing import Any

from anyio import Path
from sqlalchemy import select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models import Flow as FlowInfo
from apps.schemas.enum_var import MetadataType
from apps.schemas.flow import Flow

from .check import FileChecker
from .loader.app import AppLoader
from .loader.call import CallLoader
from .loader.flow import FlowLoader
from .loader.mcp import MCPLoader
from .loader.service import ServiceLoader

logger = logging.getLogger(__name__)


class Pool:
    """
    资源池

    在Framework启动时，执行全局的载入流程
    """

    def __init__(self) -> None:
        """初始化资源池"""
        self.app_loader = AppLoader()
        self.call_loader = CallLoader()
        self.mcp_loader = MCPLoader()
        self.service_loader = ServiceLoader()
        self.flow_loader = FlowLoader()

    @staticmethod
    async def check_dir() -> None:
        """
        检查必要的文件夹是否存在

        检查 ``data_dir`` 目录下是否存在 ``semantics/`` 目录，
        并检查是否存在 ``app/``、``service/``、``mcp/`` 目录。
        如果目录不存在，则自动创建目录。

        :return: 无
        """
        root_dir = config.deploy.data_dir.rstrip("/") + "/semantics/"
        if not await Path(root_dir + "app").exists() or not await Path(root_dir + "app").is_dir():
            logger.warning("[Pool] App目录%s不存在，创建中", root_dir + "app")
            await Path(root_dir + "app").unlink(missing_ok=True)
            await Path(root_dir + "app").mkdir(parents=True, exist_ok=True)
        if not await Path(root_dir + "service").exists() or not await Path(root_dir + "service").is_dir():
            logger.warning("[Pool] Service目录%s不存在，创建中", root_dir + "service")
            await Path(root_dir + "service").unlink(missing_ok=True)
            await Path(root_dir + "service").mkdir(parents=True, exist_ok=True)
        if not await Path(root_dir + "mcp").exists() or not await Path(root_dir + "mcp").is_dir():
            logger.warning("[Pool] MCP目录%s不存在，创建中", root_dir + "mcp")
            await Path(root_dir + "mcp").unlink(missing_ok=True)
            await Path(root_dir + "mcp").mkdir(parents=True, exist_ok=True)


    async def init(self) -> None:
        """
        加载全部文件系统内的资源

        包含：

        - 检查文件变动
        - 载入Call
        - 载入Service
        - 载入App
        - 载入MCP

        这一流程在Framework启动时执行。

        :return: 无
        """
        # 检查文件夹是否存在
        await Pool.check_dir()

        # 加载Call
        logger.info("[Pool] 载入Call")
        await self.call_loader.load()

        # 检查文件变动
        logger.info("[Pool] 检查文件变动")
        checker = FileChecker()
        changed_service, deleted_service = await checker.diff(MetadataType.SERVICE)

        # 处理Service
        logger.info("[Pool] 载入Service")

        # 批量删除
        for service in changed_service:
            await self.service_loader.delete(service, is_reload=True)
        for service in deleted_service:
            await self.service_loader.delete(service)

        # 批量加载
        for service in changed_service:
            hash_key = Path("service/" + str(service)).as_posix()
            if hash_key in checker.hashes:
                await self.service_loader.load(service, checker.hashes[hash_key])

        # 加载App
        logger.info("[Pool] 载入App")
        changed_app, deleted_app = await checker.diff(MetadataType.APP)

        # 批量删除App
        for app in changed_app:
            await self.app_loader.delete(app, is_reload=True)
        for app in deleted_app:
            await self.app_loader.delete(app)

        # 批量加载App
        for app in changed_app:
            hash_key = Path("app/" + str(app)).as_posix()
            if hash_key in checker.hashes:
                try:
                    await self.app_loader.load(app, checker.hashes[hash_key])
                except Exception as e:  # noqa: BLE001
                    await self.app_loader.delete(app, is_reload=True)
                    logger.warning("[Pool] 加载App %s 失败: %s", app, str(e))

        # 载入MCP
        logger.info("[Pool] 载入MCP")
        await self.mcp_loader.init()


    async def set_vector(self) -> None:
        """向数据库中写入向量化数据"""
        # 对所有的Loader进行向量化
        await self.call_loader.set_vector()
        await self.service_loader.set_vector()
        await self.mcp_loader.set_vector()
        await self.flow_loader.set_vector()


    async def get_flow_metadata(self, app_id: uuid.UUID) -> list[FlowInfo]:
        """从数据库中获取特定App的全部Flow的元数据"""
        async with postgres.session() as session:
            return list((await session.scalars(
                select(FlowInfo).where(FlowInfo.appId == app_id),
            )).all())


    async def get_flow(self, app_id: uuid.UUID, flow_id: str) -> Flow | None:
        """从文件系统中获取单个Flow的全部数据"""
        logger.info("[Pool] 获取工作流 %s", flow_id)
        return await self.flow_loader.load(app_id, flow_id)


    async def get_call(self, call_id: str) -> Any:
        """[Exception] 拿到Call的信息"""
        call_module = sys.modules.get("apps.scheduler.call")
        return getattr(call_module, call_id)


# 全局单例对象
pool = Pool()
