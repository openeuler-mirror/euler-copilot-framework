# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""MCP服务管理器"""

import logging
from logging import config
import random
import re
from typing import Any

from fastapi import UploadFile
from PIL import Image
from sqids.sqids import Sqids

from apps.common.mongo import MongoDB
from apps.constants import (
    ALLOWED_ICON_MIME_TYPES,
    ICON_PATH,
    SERVICE_PAGE_SIZE,
)
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.schemas.enum_var import SearchType
from apps.schemas.mcp import (
    MCPCollection,
    MCPInstallStatus,
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPTool,
    MCPType,
)
from apps.services.user import UserManager
from apps.schemas.request_data import UpdateMCPServiceRequest
from apps.schemas.response_data import MCPServiceCardItem
from apps.constants import MCP_PATH

logger = logging.getLogger(__name__)
sqids = Sqids(min_length=6)
MCP_ICON_PATH = ICON_PATH / "mcp"


class MCPServiceManager:
    """MCP服务管理器"""

    @staticmethod
    async def is_active(user_sub: str, mcp_id: str) -> bool:
        """
        判断用户是否激活MCP

        :param str user_sub: 用户ID
        :param str mcp_id: MCP服务ID
        :return: 是否激活
        """
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        mcp_list = await mcp_collection.find({"_id": mcp_id}, {"activated": True}).to_list(None)
        return any(user_sub in db_item.get("activated", []) for db_item in mcp_list)

    @staticmethod
    async def get_service_status(mcp_id: str) -> MCPInstallStatus:
        """
        获取MCP服务状态

        :param str mcp_id: MCP服务ID
        :return: MCP服务状态
        """
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        mcp_list = await mcp_collection.find({"_id": mcp_id}, {"status": True}).to_list(None)
        for db_item in mcp_list:
            status = db_item.get("status")
            if status in MCPInstallStatus.__members__.values():
                return status
        return MCPInstallStatus.FAILED

    @staticmethod
    async def fetch_mcp_services(
            search_type: SearchType,
            user_sub: str,
            keyword: str | None,
            page: int,
            is_install: bool | None = None,
            is_active: bool | None = None,
    ) -> list[MCPServiceCardItem]:
        """
        获取所有MCP服务列表

        :param search_type: SearchType: str: MCP搜索类型
        :param user_sub: str: 用户ID
        :param keyword: str: MCP搜索关键字
        :param page: int: 页码
        :return: MCP服务列表
        """
        filters = MCPServiceManager._build_filters(search_type, keyword)
        if is_active is not None:
            if is_active:
                filters["activated"] = {"$in": [user_sub]}
            else:
                filters["activated"] = {"$nin": [user_sub]}
        user_info = await UserManager.get_userinfo_by_user_sub(user_sub)
        if not user_info.is_admin:
            filters["status"] = MCPInstallStatus.READY.value
        else:
            if is_install is not None:
                if is_install:
                    filters["status"] = MCPInstallStatus.READY.value
                else:
                    filters["status"] = {"$ne": MCPInstallStatus.READY.value}
        mcpservice_pools = await MCPServiceManager._search_mcpservice(filters, page)
        return [
            MCPServiceCardItem(
                mcpserviceId=item.id,
                icon=await MCPLoader.get_icon(item.id),
                name=item.name,
                description=item.description,
                author=item.author,
                isActive=await MCPServiceManager.is_active(user_sub, item.id),
                status=await MCPServiceManager.get_service_status(item.id),
            )
            for item in mcpservice_pools
        ]

    @staticmethod
    async def get_mcp_service(mcpservice_id: str) -> MCPCollection:
        """
        获取MCP服务详细信息

        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务详细信息
        """
        # 验证用户权限
        mcpservice_collection = MongoDB().get_collection("mcp")
        db_service = await mcpservice_collection.find_one({"_id": mcpservice_id})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到"
            raise RuntimeError(msg)
        return MCPCollection.model_validate(db_service)

    @staticmethod
    async def get_mcp_config(mcpservice_id: str) -> tuple[MCPServerConfig, str]:
        """
        获取MCP服务配置

        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务配置
        """
        icon = await MCPLoader.get_icon(mcpservice_id)
        config = await MCPLoader.get_config(mcpservice_id)
        return config, icon

    @staticmethod
    async def get_service_tools(
            service_id: str,
    ) -> list[MCPTool]:
        """
        获取MCP可以用工具

        :param service_id: str: MCP服务ID
        :return: MCP工具详细信息列表
        """
        # 获取服务名称
        service_collection = MongoDB().get_collection("mcp")
        data = await service_collection.find({"_id": service_id}, {"tools": True}).to_list(None)
        result = []
        for item in data:
            for tool in item.get("tools", {}):
                tool_data = MCPTool.model_validate(tool)
                result.append(tool_data)
        return result

    @staticmethod
    async def _search_mcpservice(
            search_conditions: dict[str, Any],
            page: int,
    ) -> list[MCPCollection]:
        """
        基于输入条件搜索MCP服务

        :param search_conditions: dict[str, Any]: 搜索条件
        :param page: int: 页码
        :return: MCP列表
        """
        mcpservice_collection = MongoDB().get_collection("mcp")
        # 分页查询
        skip = (page - 1) * SERVICE_PAGE_SIZE
        db_mcpservices = await mcpservice_collection.find(search_conditions).skip(skip).limit(
            SERVICE_PAGE_SIZE,
        ).to_list()
        # 如果未找到，返回空列表
        if not db_mcpservices:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_conditions)
            return []
        # 将数据库中的MCP服务转换为对象
        return [MCPCollection.model_validate(db_mcpservice) for db_mcpservice in db_mcpservices]

    @staticmethod
    def _build_filters(
            search_type: SearchType,
            keyword: str | None,
    ) -> dict[str, Any]:
        if not keyword:
            return {}

        if search_type == SearchType.ALL:
            base_filters = {"$or": [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
                {"author": {"$regex": keyword, "$options": "i"}},
            ]}
        elif search_type == SearchType.NAME:
            base_filters = {"name": {"$regex": keyword, "$options": "i"}}
        elif search_type == SearchType.DESCRIPTION:
            base_filters = {"description": {"$regex": keyword, "$options": "i"}}
        elif search_type == SearchType.AUTHOR:
            base_filters = {"author": {"$regex": keyword, "$options": "i"}}
        return base_filters

    @staticmethod
    async def create_mcpservice(data: UpdateMCPServiceRequest, user_sub: str) -> str:
        """
        创建MCP服务

        :param UpdateMCPServiceRequest data: MCP服务配置
        :return: MCP服务ID
        """
        # 检查config
        if data.mcp_type == MCPType.SSE:
            config = MCPServerSSEConfig.model_validate(data.config)
        else:
            config = MCPServerStdioConfig.model_validate(data.config)

        # 构造Server
        mcp_server = MCPServerConfig(
            name=await MCPServiceManager.clean_name(data.name),
            overview=data.overview,
            description=data.description,
            config=config,
            type=data.mcp_type,
            author=user_sub,
        )

        # 检查是否存在相同服务
        mcp_collection = MongoDB().get_collection("mcp")
        db_service = await mcp_collection.find_one({"name": mcp_server.name})
        mcp_id = sqids.encode([random.randint(0, 1000000) for _ in range(5)])[:6]  # noqa: S311
        if db_service:
            mcp_server.name = f"{mcp_server.name}-{mcp_id}"
            logger.warning("[MCPServiceManager] 已存在相同名称和描述的MCP服务")

        # 保存并载入配置
        logger.info("[MCPServiceManager] 创建mcp：%s", mcp_server.name)
        mcp_path = MCP_PATH / "template" / mcp_id / "project"
        if isinstance(config, MCPServerStdioConfig):
            index = None
            for i in range(len(config.args)):
                if not config.args[i] == "--directory":
                    continue
                index = i + 1
                break
            if index is not None:
                if index >= len(config.args):
                    config.args.append(str(mcp_path))
                else:
                    config.args[index] = str(mcp_path)
            else:
                config.args += ["--directory", str(mcp_path)]
        await MCPLoader._insert_template_db(mcp_id=mcp_id, config=mcp_server)
        await MCPLoader.save_one(mcp_id, mcp_server)
        await MCPLoader.update_template_status(mcp_id, MCPInstallStatus.INIT)
        return mcp_id

    @staticmethod
    async def update_mcpservice(data: UpdateMCPServiceRequest, user_sub: str) -> str:
        """
        更新MCP服务

        :param UpdateMCPServiceRequest data: MCP服务配置
        :return: MCP服务ID
        """
        if not data.service_id:
            msg = "[MCPServiceManager] MCP服务ID为空"
            raise ValueError(msg)

        mcp_collection = MongoDB().get_collection("mcp")
        db_service = await mcp_collection.find_one({"_id": data.service_id, "author": user_sub})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到或无权限"
            raise ValueError(msg)

        db_service = MCPCollection.model_validate(db_service)
        mcp_config = MCPServerConfig(
            name=data.name,
            overview=data.overview,
            description=data.description,
            config=MCPServerStdioConfig.model_validate(
                data.config,
            ) if data.mcp_type == MCPType.STDIO else MCPServerSSEConfig.model_validate(
                data.config,
            ),
            type=data.mcp_type,
            author=user_sub,
        )
        old_mcp_config = await MCPLoader.get_config(data.service_id)
        await MCPLoader._insert_template_db(mcp_id=data.service_id, config=mcp_config)
        await MCPLoader.save_one(mcp_id=data.service_id, config=mcp_config)
        if old_mcp_config.type != mcp_config.type or old_mcp_config.config != mcp_config.config:
            for user_id in db_service.activated:
                await MCPServiceManager.deactive_mcpservice(user_sub=user_id, service_id=data.service_id)
            await MCPLoader.update_template_status(data.service_id, MCPInstallStatus.INIT)
        # 返回服务ID
        return data.service_id

    @staticmethod
    async def delete_mcpservice(service_id: str) -> None:
        """
        删除MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 是否删除成功
        """
        # 删除对应的mcp
        await MCPLoader.delete_mcp(service_id)

        # 遍历所有应用，将其中的MCP依赖删除
        app_collection = MongoDB().get_collection("application")
        await app_collection.update_many(
            {"mcp_service": service_id},
            {"$pull": {"mcp_service": service_id}},
        )

    @staticmethod
    async def active_mcpservice(
            user_sub: str,
            service_id: str,
            mcp_env: dict[str, Any] | None = None,
    ) -> None:
        """
        激活MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 无
        """
        mcp_collection = MongoDB().get_collection("mcp")
        status = await mcp_collection.find({"_id": service_id}, {"status": 1}).to_list()
        for item in status:
            mcp_status = item.get("status", MCPInstallStatus.INSTALLING)
            if mcp_status == MCPInstallStatus.READY:
                await MCPLoader.user_active_template(user_sub, service_id, mcp_env)
            else:
                err = "[MCPServiceManager] MCP服务未准备就绪"
                raise RuntimeError(err)

    @staticmethod
    async def deactive_mcpservice(
            user_sub: str,
            service_id: str,
    ) -> None:
        """
        取消激活MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 无
        """
        mcp_pool = MCPPool()
        try:
            await mcp_pool.stop(mcp_id=service_id, user_sub=user_sub)
        except KeyError:
            logger.warning("[MCPServiceManager] MCP服务无进程")
        await MCPLoader.user_deactive_template(user_sub, service_id)

    @staticmethod
    async def clean_name(name: str) -> str:
        """
        移除MCP服务名称中的特殊字符

        :param name: str: MCP服务名称
        :return: 清理后的MCP服务名称
        """
        invalid_chars = r'[\\\/:*?"<>|]'
        return re.sub(invalid_chars, "_", name)

    @staticmethod
    async def save_mcp_icon(
            service_id: str,
            icon: UploadFile,
    ) -> str:
        """保存MCP服务图标"""
        # 检查MIME
        import magic
        mime = magic.from_buffer(icon.file.read(), mime=True)
        icon.file.seek(0)

        if mime not in ALLOWED_ICON_MIME_TYPES:
            err = "[MCPServiceManager] 不支持的图标格式"
            raise ValueError(err)

        # 保存图标
        image = Image.open(icon.file)
        image = image.convert("RGB")
        image = image.resize((64, 64), resample=Image.Resampling.LANCZOS)
        # 检查文件夹
        image_path = MCP_PATH / "template" / service_id / "icon"
        if not await image_path.exists():
            await image_path.mkdir(parents=True, exist_ok=True)
        # 保存
        image.save(image_path / f"{service_id}.png", format="PNG", optimize=True, compress_level=9)

        return f"{image_path / f'{service_id}.png'}"

    @staticmethod
    async def install_mcpservice(user_sub: str, service_id: str, install: bool) -> None:
        """
        安装或卸载MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :param install: bool: 是否安装
        :return: 无
        """
        service_collection = MongoDB().get_collection("mcp")
        db_service = await service_collection.find_one({"_id": service_id, "author": user_sub})
        db_service = MCPCollection.model_validate(db_service)
        if install:
            if db_service.status == MCPInstallStatus.INSTALLING:
                err = "[MCPServiceManager] MCP服务已处于安装中"
                raise Exception(err)
            await service_collection.update_one(
                {"_id": service_id},
                {"$set": {"status": MCPInstallStatus.INSTALLING}},
            )
            mcp_config = await MCPLoader.get_config(service_id)
            await MCPLoader.init_one_template(mcp_id=service_id, config=mcp_config)
        else:
            await MCPLoader.cancel_installing_task([service_id])
