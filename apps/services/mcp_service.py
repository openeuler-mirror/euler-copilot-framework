# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP服务（插件中心）管理"""

import logging
import re
import uuid
from typing import Any

import magic
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import and_, delete, or_, select

from apps.common.postgres import postgres
from apps.constants import (
    ALLOWED_ICON_MIME_TYPES,
    ICON_PATH,
    MCP_PATH,
    SERVICE_PAGE_SIZE,
)
from apps.models import (
    MCPActivated,
    MCPInfo,
    MCPInstallStatus,
    MCPTools,
    MCPType,
)
from apps.models.app import AppMCP
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.mcp.pool import mcp_pool
from apps.schemas.enum_var import SearchType
from apps.schemas.mcp import (
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    UpdateMCPServiceRequest,
)
from apps.schemas.mcp_service import MCPServiceCardItem
from apps.services.user import UserManager

logger = logging.getLogger(__name__)
MCP_ICON_PATH = ICON_PATH / "mcp"


class MCPServiceManager:
    """MCP服务管理"""

    @staticmethod
    async def is_active(user_id: str, mcp_id: str) -> bool:
        """判断用户是否激活MCP"""
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPActivated).where(
                and_(
                    MCPActivated.mcpId == mcp_id,
                    MCPActivated.userId == user_id,
                ),
            ))).one_or_none()
            return bool(mcp_info)


    @staticmethod
    async def get_icon_path(mcp_id: str) -> str:
        """获取MCP服务图标路径"""
        if (MCP_ICON_PATH / f"{mcp_id}.png").exists():
            return f"/static/mcp/{mcp_id}.png"
        return ""


    @staticmethod
    async def get_service_status(mcp_id: str) -> MCPInstallStatus:
        """获取MCP服务状态"""
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_id))).one_or_none()
            if mcp_info:
                return mcp_info.status
            return MCPInstallStatus.FAILED


    @staticmethod
    async def fetch_mcp_services(  # noqa: PLR0913
            search_type: SearchType,
            user_id: str,
            keyword: str | None,
            page: int,
            *,
            is_install: bool | None = None,
            is_active: bool | None = None,
    ) -> list[MCPServiceCardItem]:
        """获取所有MCP服务列表"""
        mcpservice_pools = await MCPServiceManager._search_mcpservice(
            search_type, keyword, page, user_id, is_active=is_active, is_installed=is_install,
        )

        author_ids = {item.authorId for item in mcpservice_pools}
        author_names = await UserManager.get_usernames_by_ids(author_ids)

        return [
            MCPServiceCardItem(
                mcpserviceId=item.id,
                icon=await MCPServiceManager.get_icon_path(item.id),
                name=item.name,
                description=item.description,
                author=author_names.get(item.authorId, item.authorId),
                isActive=await MCPServiceManager.is_active(user_id, item.id),
                status=await MCPServiceManager.get_service_status(item.id),
            )
            for item in mcpservice_pools
        ]


    @staticmethod
    async def get_mcp_service(mcp_id: str) -> MCPInfo | None:
        """获取MCP服务详细信息"""
        async with postgres.session() as session:
            return (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_id))).one_or_none()


    @staticmethod
    async def get_mcp_config(mcp_id: str) -> tuple[MCPServerConfig, str]:
        """获取MCP服务配置"""
        icon_path = ""
        config = await MCPLoader.get_config(mcp_id)
        return config, icon_path


    @staticmethod
    async def get_mcp_tools(mcp_id: str) -> list[MCPTools]:
        """获取MCP可用工具"""
        async with postgres.session() as session:
            return list((await session.scalars(select(MCPTools).where(MCPTools.mcpId == mcp_id))).all())


    @staticmethod
    async def _build_search_conditions(
            search_type: SearchType,
            keyword: str | None,
            author_user_ids: list[str],
    ) -> Any | None:
        """构建搜索条件"""
        if search_type == SearchType.ALL:
            conditions = [
                MCPInfo.name.like(f"%{keyword}%"),
                MCPInfo.description.like(f"%{keyword}%"),
            ]
            if author_user_ids:
                conditions.append(MCPInfo.authorId.in_(author_user_ids))
            return or_(*conditions)

        if search_type == SearchType.NAME:
            return MCPInfo.name.like(f"%{keyword}%")

        if search_type == SearchType.DESCRIPTION:
            return MCPInfo.description.like(f"%{keyword}%")

        if author_user_ids:
            return MCPInfo.authorId.in_(author_user_ids)
        return None


    @staticmethod
    def _apply_user_filters(
            sql: Any,
            user_id: str,
            *,
            is_active: bool | None = None,
            is_installed: bool | None = None,
    ) -> Any:
        """应用用户过滤条件"""
        if is_installed is not None:
            sql = sql.where(MCPInfo.id.in_(
                select(MCPActivated.mcpId).where(MCPActivated.userId == user_id),
            ))
        if is_active is not None:
            sql = sql.where(MCPInfo.id.in_(
                select(MCPActivated.mcpId).where(MCPActivated.userId == user_id),
            ))
        return sql


    @staticmethod
    async def _search_mcpservice(  # noqa: PLR0913
            search_type: SearchType,
            keyword: str | None,
            page: int,
            user_id: str,
            *,
            is_active: bool | None = None,
            is_installed: bool | None = None,
    ) -> list[MCPInfo]:
        """基于输入条件搜索MCP服务"""
        skip = (page - 1) * SERVICE_PAGE_SIZE

        author_user_ids = []
        if keyword and search_type in (SearchType.ALL, SearchType.AUTHOR):
            author_user_ids = await UserManager.get_user_ids_by_username_keyword(keyword)

        search_conditions = await MCPServiceManager._build_search_conditions(
            search_type, keyword, author_user_ids,
        )
        if search_conditions is None:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_type)
            return []

        async with postgres.session() as session:
            sql = select(MCPInfo).where(search_conditions)
            sql = MCPServiceManager._apply_user_filters(
                sql, user_id, is_active=is_active, is_installed=is_installed,
            )
            sql = sql.offset(skip).limit(SERVICE_PAGE_SIZE)
            result = list((await session.scalars(sql)).all())

        if not result:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_type)

        return result


    @staticmethod
    async def create_mcpservice(data: UpdateMCPServiceRequest, user_id: str) -> str:
        """创建MCP服务"""
        if data.mcp_type == MCPType.SSE:
            config = MCPServerSSEConfig.model_validate(data.config)
        else:
            config = MCPServerStdioConfig.model_validate(data.config)

        mcp_server = MCPServerConfig(
            name=await MCPServiceManager.clean_name(data.name),
            overview=data.overview,
            description=data.description,
            mcpServers={
                data.mcp_id: config,
            },
            mcpType=data.mcp_type,
            author=user_id,
        )

        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.name == mcp_server.name))).one_or_none()
            if mcp_info:
                mcp_server.name = f"{mcp_server.name}-{uuid.uuid4().hex[:6]}"
                logger.warning("[MCPServiceManager] 已存在相同ID或名称的MCP服务")

        logger.info("[MCPServiceManager] 创建mcp: %s", mcp_server.name)
        mcp_path = MCP_PATH / "template" / data.mcp_id / "project"
        index = None
        if isinstance(config, MCPServerStdioConfig):
            index = None
            for i in range(len(config.args)):
                if config.args[i] != "--directory":
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
        async with postgres.session() as session:
            await session.merge(MCPInfo(
                id=data.mcp_id,
                name=mcp_server.name,
                overview=mcp_server.overview,
                description=mcp_server.description,
                mcpType=mcp_server.mcpType,
                authorId=mcp_server.author or "",
            ))
            await session.commit()
        await MCPLoader.save_one(data.mcp_id, mcp_server)
        await MCPLoader.update_template_status(data.mcp_id, MCPInstallStatus.INIT)
        return data.mcp_id


    @staticmethod
    async def update_mcpservice(data: UpdateMCPServiceRequest, user_id: str) -> str:
        """更新MCP服务"""
        if not data.mcp_id:
            msg = "[MCPServiceManager] MCP服务ID为空"
            raise ValueError(msg)

        async with postgres.session() as session:
            db_service = (await session.scalars(select(MCPInfo).where(
                and_(
                    MCPInfo.id == data.mcp_id,
                    MCPInfo.authorId == user_id,
                ),
            ))).one_or_none()
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到或无权限"
            raise ValueError(msg)

        async with postgres.session() as session:
            activated_users = (await session.scalars(select(MCPActivated).where(
                MCPActivated.mcpId == data.mcp_id,
            ))).all()

        for activated_user in activated_users:
            await MCPServiceManager.deactive_mcpservice(user_id=activated_user.userId, mcp_id=data.mcp_id)

        mcp_config = MCPServerConfig(
            name=data.name,
            overview=data.overview,
            description=data.description,
            mcpServers={
                data.mcp_id: data.config[data.mcp_id],
            },
            mcpType=data.mcp_type,
            author=user_id,
        )
        async with postgres.session() as session:
            await session.merge(MCPInfo(
                id=data.mcp_id,
                name=mcp_config.name,
                overview=mcp_config.overview,
                description=mcp_config.description,
                mcpType=mcp_config.mcpType,
                authorId=mcp_config.author or "",
            ))
            await session.commit()
        await MCPLoader.save_one(mcp_id=data.mcp_id, config=mcp_config)
        await MCPLoader.update_template_status(data.mcp_id, MCPInstallStatus.INIT)
        return data.mcp_id


    @staticmethod
    async def delete_mcpservice(mcp_id: str) -> None:
        """删除MCP服务"""
        await MCPLoader.delete_mcp(mcp_id)

        async with postgres.session() as session:
            stmt = delete(AppMCP).where(AppMCP.mcpId == mcp_id)
            await session.execute(stmt)
            await session.commit()


    @staticmethod
    async def active_mcpservice(
            user_id: str,
            mcp_id: str,
            mcp_env: dict[str, Any] | None = None,
    ) -> None:
        """激活MCP服务"""
        if mcp_env is None:
            mcp_env = {}

        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_id))).one_or_none()
            if not mcp_info:
                err = "[MCPServiceManager] MCP服务未找到"
                raise ValueError(err)
            if mcp_info.status != MCPInstallStatus.READY:
                err = "[MCPServiceManager] MCP服务未准备就绪"
                raise RuntimeError(err)
        await MCPLoader.user_active_template(user_id, mcp_id, mcp_env)


    @staticmethod
    async def deactive_mcpservice(
            user_id: str,
            mcp_id: str,
    ) -> None:
        """取消激活MCP服务"""
        try:
            await mcp_pool.stop(mcp_id=mcp_id, user_id=user_id)
        except KeyError:
            logger.warning("[MCPServiceManager] MCP服务无进程")
        await MCPLoader.user_deactive_template(user_id, mcp_id)


    @staticmethod
    async def clean_name(name: str) -> str:
        """移除MCP服务名称中的特殊字符"""
        invalid_chars = r'[\\\/:*?"<>|]'
        return re.sub(invalid_chars, "_", name)


    @staticmethod
    async def save_mcp_icon(
            mcp_id: str,
            icon: UploadFile,
    ) -> str:
        """保存MCP服务图标"""
        mime = magic.from_buffer(icon.file.read(), mime=True)
        icon.file.seek(0)

        if mime not in ALLOWED_ICON_MIME_TYPES:
            err = "[MCPServiceManager] 不支持的图标格式"
            raise ValueError(err)

        image = Image.open(icon.file)
        image = image.convert("RGB")
        image = image.resize((64, 64), resample=Image.Resampling.LANCZOS)
        if not await MCP_ICON_PATH.exists():
            await MCP_ICON_PATH.mkdir(parents=True, exist_ok=True)
        image.save(MCP_ICON_PATH / f"{mcp_id}.png", format="PNG", optimize=True, compress_level=9)

        return f"/static/mcp/{mcp_id}.png"


    @staticmethod
    async def is_user_actived(user_id: str, mcp_id: str) -> bool:
        """判断用户是否激活MCP"""
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPActivated).where(
                and_(
                    MCPActivated.mcpId == mcp_id,
                    MCPActivated.userId == user_id,
                ),
            ))).one_or_none()
            return bool(mcp_info)


    @staticmethod
    async def query_mcp_tools(mcp_id: str) -> list[MCPTools]:
        """查询MCP工具"""
        async with postgres.session() as session:
            return list((await session.scalars(select(MCPTools).where(MCPTools.mcpId == mcp_id))).all())


    @staticmethod
    async def install_mcpservice(user_id: str, service_id: str, *, install: bool) -> None:
        """安装或卸载MCP服务"""
        async with postgres.session() as session:
            db_service = (await session.scalars(select(MCPInfo).where(
                and_(
                    MCPInfo.id == service_id,
                    MCPInfo.authorId == user_id,
                ),
            ))).one_or_none()

        if not db_service:
            err = "[MCPServiceManager] MCP服务未找到或无权限"
            raise ValueError(err)

        if install:
            if db_service.status == MCPInstallStatus.INSTALLING:
                err = "[MCPServiceManager] MCP服务已处于安装中"
                raise RuntimeError(err)
            mcp_config = await MCPLoader.get_config(service_id)
            await MCPLoader.init_one_template(mcp_id=service_id, config=mcp_config)
        else:
            if db_service.status != MCPInstallStatus.INSTALLING:
                err = "[MCPServiceManager] 只能卸载处于安装中的MCP服务"
                raise RuntimeError(err)
            await MCPLoader.cancel_installing_task([service_id])
