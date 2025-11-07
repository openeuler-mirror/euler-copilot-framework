# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 加载器；下属于MCP Pool"""

import json
import logging
import shutil
from typing import Any

import asyncer
from anyio import Path
from sqlalchemy import and_, delete, select, text, update

from apps.common.postgres import Postgres, postgres
from apps.common.process_handler import ProcessHandler
from apps.constants import MCP_PATH
from apps.llm.embedding import embedding
from apps.models.mcp import MCPActivated, MCPInfo, MCPInstallStatus, MCPTools, MCPType
from apps.scheduler.pool.mcp.client import MCPClient
from apps.scheduler.pool.mcp.install import install_npx, install_uvx
from apps.schemas.mcp import (
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
)

logger = logging.getLogger(__name__)


class MCPLoader:
    """
    MCP加载模块

    创建MCP Client，启动MCP进程，并将MCP基本信息（名称、描述、工具列表等）写入数据库
    """

    @staticmethod
    async def _init_embedding_for_task(pg: Postgres) -> None:
        """
        为安装任务初始化 embedding 单例

        :param Postgres pg: PostgreSQL实例
        :return: 无
        """
        try:
            from apps.models import GlobalSettings  # noqa: PLC0415
            from apps.services.llm import LLMManager  # noqa: PLC0415

            async with pg.session() as session:
                from sqlalchemy import select  # noqa: PLC0415
                settings = (await session.scalars(select(GlobalSettings))).first()
                if settings and settings.embeddingLlmId:
                    embedding_llm_config = await LLMManager.get_llm(settings.embeddingLlmId)
                    if embedding_llm_config:
                        await embedding.init(embedding_llm_config)
                        logger.info("[Installer] Embedding单例已初始化")
        except Exception as e:  # noqa: BLE001
            logger.warning("[Installer] 初始化Embedding单例失败: %s", str(e))

    @staticmethod
    async def _check_vector_table_exists(pg: Postgres = postgres) -> bool:
        """
        检查向量表是否存在

        :param Postgres pg: PostgreSQL实例，默认为全局单例postgres
        :return: 向量表是否存在
        :rtype: bool
        """
        async with pg.session() as session:
            try:
                result = await session.execute(
                    text(
                        "SELECT EXISTS ("
                        "  SELECT FROM information_schema.tables "
                        "  WHERE table_schema = 'public' "
                        "  AND table_name = 'framework_mcp_tool_vector'"
                        ")",
                    ),
                )
                exists = result.scalar()
                return bool(exists)
            except Exception as e:  # noqa: BLE001
                logger.debug("[MCPLoader] 检查向量表失败: %s", e)
                return False

    @staticmethod
    async def _check_dir() -> None:
        """
        检查MCP目录是否存在

        :return: 无
        """
        if not await (MCP_PATH / "template").exists() or not await (MCP_PATH / "template").is_dir():
            logger.warning("[MCPLoader] template目录不存在，创建中")
            await (MCP_PATH / "template").unlink(missing_ok=True)
            await (MCP_PATH / "template").mkdir(parents=True, exist_ok=True)

        if not await (MCP_PATH / "users").exists() or not await (MCP_PATH / "users").is_dir():
            logger.warning("[MCPLoader] users目录不存在，创建中")
            await (MCP_PATH / "users").unlink(missing_ok=True)
            await (MCP_PATH / "users").mkdir(parents=True, exist_ok=True)


    @staticmethod
    async def _install_stdio_mcp(
        mcp_id: str,
        mcp_config: MCPServerStdioConfig,
        item: MCPServerConfig,
    ) -> MCPServerStdioConfig | None:
        """
        安装 Stdio 类型的 MCP

        :param str mcp_id: MCP模板ID
        :param MCPServerStdioConfig mcp_config: MCP配置
        :param MCPServerConfig item: 完整的配置对象
        :return: 安装后的配置，失败返回None
        :rtype: MCPServerStdioConfig | None
        """
        print(f"[Installer] Stdio方式的MCP模板，开始自动安装: {mcp_id}")  # noqa: T201
        if "uv" in mcp_config.command:
            updated_config = await install_uvx(mcp_id, mcp_config)
        elif "npx" in mcp_config.command:
            updated_config = await install_npx(mcp_id, mcp_config)
        else:
            return mcp_config

        if updated_config is None:
            return None

        item.mcpServers[mcp_id] = updated_config
        template_config = MCP_PATH / "template" / mcp_id / "config.json"
        f = await template_config.open("w+", encoding="utf-8")
        config_data = item.model_dump(by_alias=True, exclude_none=True)
        await f.write(json.dumps(config_data, indent=4, ensure_ascii=False))
        await f.aclose()
        return updated_config

    @staticmethod
    async def _handle_tool_vectorization(
        mcp_id: str,
        item: MCPServerConfig,
        tool_list: list[MCPTools],
        pg: Postgres,
    ) -> None:
        """
        处理工具向量化

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig item: MCP配置
        :param list[MCPTools] tool_list: 工具列表
        :param Postgres pg: PostgreSQL实例
        :return: 无
        """
        if not await MCPLoader._check_vector_table_exists(pg):
            logger.warning("[Installer] 向量表不存在，跳过MCP工具向量化: %s", mcp_id)
            return

        if not tool_list:
            logger.warning("[Installer] 工具列表为空，跳过MCP工具向量化: %s", mcp_id)
            return

        if embedding.MCPVector is None or embedding.MCPToolVector is None:
            logger.warning("[Installer] 向量表类未初始化，跳过MCP工具向量化: %s", mcp_id)
            return

        try:
            logger.info("[Installer] 开始向量化MCP工具: %s", mcp_id)

            tool_desc_list = [tool.description for tool in tool_list]
            mcp_embedding = await embedding.get_embedding([item.description])
            tool_embedding = await embedding.get_embedding(tool_desc_list)

            async with pg.session() as session:
                await session.execute(delete(embedding.MCPVector).where(embedding.MCPVector.id == mcp_id))
                await session.execute(
                    delete(embedding.MCPToolVector).where(embedding.MCPToolVector.mcpId == mcp_id),
                )
                session.add(embedding.MCPVector(
                    id=mcp_id,
                    embedding=mcp_embedding[0],
                ))
                for tool, emb in zip(tool_list, tool_embedding, strict=True):
                    session.add(embedding.MCPToolVector(
                        id=tool.id,
                        mcpId=mcp_id,
                        embedding=emb,
                    ))
                await session.commit()

            logger.info("[Installer] MCP工具向量化完成: %s", mcp_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[Installer] MCP工具向量化失败: %s, 错误: %s", mcp_id, str(e))

    @staticmethod
    async def _load_config(config_path: Path) -> MCPServerConfig:
        """
        加载 MCP 配置

        :param Path config_path: MCP配置文件路径
        :return: MCP配置
        :raises FileNotFoundError: 如果配置文件不存在，则抛出异常
        """
        if not await config_path.exists():
            err = f"MCP配置文件不存在: {config_path}"
            logger.error(err)
            raise FileNotFoundError(err)

        f = await config_path.open("r", encoding="utf-8")
        f_content = json.loads(await f.read())
        await f.aclose()

        return MCPServerConfig.model_validate(f_content)


    @staticmethod
    async def _install_template_task(item: MCPServerConfig) -> None:
        """
        安装依赖；此函数在子进程中运行

        :param MCPServerConfig config: MCP配置
        :return: 无
        """
        await postgres.init()
        await MCPLoader._init_embedding_for_task(postgres)

        mcp_id = next(iter(item.mcpServers.keys()))
        mcp_config = item.mcpServers[mcp_id]

        try:
            if not mcp_config.autoInstall:
                print(f"[Installer] MCP模板无需安装: {mcp_id}")  # noqa: T201
            elif isinstance(mcp_config, MCPServerStdioConfig):
                updated_config = await MCPLoader._install_stdio_mcp(mcp_id, mcp_config, item)
                if updated_config is None:
                    logger.error("[MCPLoader] MCP模板安装失败: %s", mcp_id)
                    await MCPLoader.update_template_status(mcp_id, MCPInstallStatus.FAILED, postgres)
                    return
                mcp_config = updated_config
            else:
                logger.info("[Installer] SSE/StreamableHTTP方式的MCP模板，无需安装: %s", mcp_id)
                item.mcpServers[mcp_id].autoInstall = False

            tool_list = await MCPLoader._get_template_tool(mcp_id, item)

            async with postgres.session() as session:
                if await MCPLoader._check_vector_table_exists(postgres) and embedding.MCPToolVector is not None:
                    await session.execute(
                        delete(embedding.MCPToolVector).where(embedding.MCPToolVector.mcpId == mcp_id),
                    )

                await session.execute(delete(MCPTools).where(MCPTools.mcpId == mcp_id))
                session.add_all(tool_list)
                await session.commit()

            await MCPLoader._handle_tool_vectorization(mcp_id, item, tool_list, postgres)

            await MCPLoader.update_template_status(mcp_id, MCPInstallStatus.READY, postgres)
            logger.info("[Installer] MCP模板安装成功: %s", mcp_id)
        except Exception:
            logger.exception("[MCPLoader] MCP模板安装失败: %s", mcp_id)
            await MCPLoader.update_template_status(mcp_id, MCPInstallStatus.FAILED, postgres)
            raise
        finally:
            await postgres.close()


    @staticmethod
    async def clear_ready_or_failed_mcp_installation() -> None:
        """清除状态为ready或failed的MCP安装任务"""
        mcp_ids = ProcessHandler.get_all_task_ids()
        async with postgres.session() as session:
            result = await session.scalars(
                select(MCPInfo).where(
                    and_(
                        MCPInfo.id.in_(mcp_ids),
                        MCPInfo.status.in_([MCPInstallStatus.READY, MCPInstallStatus.FAILED]),
                    ),
                ),
            )
            db_service_list = list(result.all())
            for db_service in db_service_list:
                ProcessHandler.remove_task(db_service.id)
                logger.info("[MCPLoader] 删除已完成或失败的MCP安装进程: %s", db_service.id)


    @staticmethod
    async def init_one_template(mcp_id: str, config: MCPServerConfig) -> None:
        """
        初始化单个MCP模板

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig config: MCP配置
        :return: 无
        """
        await MCPLoader.clear_ready_or_failed_mcp_installation()

        if len(config.mcpServers) > 1:
            err = f'[MCPLoader] MCP模板"{mcp_id}"包含多个MCP Server，无法初始化'
            logger.error(err)
            raise ValueError(err)

        await MCPLoader._insert_template_db(mcp_id, config)

        template_path = MCP_PATH / "template" / str(mcp_id)
        await Path.mkdir(template_path, parents=True, exist_ok=True)

        if not ProcessHandler.add_task(mcp_id, MCPLoader._install_template_task, config):
            err = f"安装任务无法执行，请稍后重试: {mcp_id}"
            logger.error(err)
            raise RuntimeError(err)


    @staticmethod
    async def cancel_all_installing_task() -> None:
        """取消正在安装的MCP模板任务"""
        template_path = MCP_PATH / "template"
        logger.info("[MCPLoader] 取消正在安装的MCP模板任务: %s", template_path)

        mcp_configs = await MCPLoader._get_all_mcp_configs()
        mcp_ids = list(mcp_configs.keys())

        async with postgres.session() as session:
            await session.execute(
                update(MCPInfo).where(
                    and_(
                        MCPInfo.status == MCPInstallStatus.INSTALLING,
                        MCPInfo.id.in_(mcp_ids),
                    ),
                ).values(status=MCPInstallStatus.CANCELLED),
            )
            await session.commit()


    @staticmethod
    async def _get_all_mcp_configs() -> dict[str, MCPServerConfig]:
        """
        获取所有MCP模板的配置

        :return: MCP ID到配置的映射
        """
        mcp_configs = {}
        template_path = MCP_PATH / "template"

        async for mcp_dir in template_path.iterdir():
            if not await mcp_dir.is_dir():
                logger.warning("[MCPLoader] 跳过非目录: %s", mcp_dir.as_posix())
                continue

            config_path = mcp_dir / "config.json"
            if not await config_path.exists():
                logger.warning("[MCPLoader] 跳过没有配置文件的MCP模板: %s", mcp_dir.as_posix())
                continue

            try:
                config = await MCPLoader._load_config(config_path)
                mcp_configs[mcp_dir.name] = config
            except Exception as e:  # noqa: BLE001
                logger.warning("[MCPLoader] 加载MCP配置失败: %s, 错误: %s", mcp_dir.name, str(e))
                continue

        return mcp_configs

    @staticmethod
    async def _init_all_template() -> None:
        """
        初始化所有文件夹中的MCP模板

        遍历 ``template`` 目录下的所有MCP模板，并初始化。在Framework启动时进行此流程，确保所有MCP均可正常使用。
        这一过程会与数据库内的条目进行对比，若发生修改，则重新创建数据库条目。
        """
        template_path = MCP_PATH / "template"
        logger.info("[MCPLoader] 初始化所有MCP模板: %s", template_path)

        mcp_configs = await MCPLoader._get_all_mcp_configs()
        for mcp_id, config in mcp_configs.items():
            logger.info("[MCPLoader] 初始化MCP模板: %s", mcp_id)
            await MCPLoader.init_one_template(mcp_id, config)


    @staticmethod
    async def _get_template_tool(
            mcp_id: str,
            config: MCPServerConfig,
            user_id: str | None = None,
    ) -> list[MCPTools]:
        """
        获取MCP模板的工具列表

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig config: MCP配置
        :param str | None user_id: 用户ID,默认为None
        :return: 工具列表
        :rtype: list[str]
        """
        if (
            (config.mcpType == MCPType.STDIO and isinstance(config.mcpServers[mcp_id], MCPServerStdioConfig))
            or (config.mcpType == MCPType.SSE and isinstance(config.mcpServers[mcp_id], MCPServerSSEConfig))
        ):
            client = MCPClient()
        else:
            err = f"MCP {mcp_id}：未知的MCP服务类型“{config.mcpType}”"
            logger.error(err)
            raise ValueError(err)

        await client.init(user_id, mcp_id, config.mcpServers[mcp_id])

        tool_list = []
        for item in client.tools:
            tool_list += [MCPTools(
                mcpId=mcp_id,
                toolName=item.name,
                description=item.description or "",
                inputSchema=item.inputSchema,
                outputSchema=item.outputSchema or {},
            )]
        await client.stop()
        return tool_list


    @staticmethod
    async def _insert_template_db(mcp_id: str, config: MCPServerConfig) -> None:
        """
        插入单个MCP Server信息到数据库，供前端展示

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig config: MCP配置
        :return: 无
        """
        async with postgres.session() as session:
            await session.merge(MCPInfo(
                id=mcp_id,
                name=config.name,
                overview=config.overview,
                description=config.description,
                mcpType=config.mcpType,
                authorId=config.author or "",
            ))
            await session.commit()


    @staticmethod
    async def save_one(mcp_id: str, config: MCPServerConfig) -> None:
        """
        保存单个MCP模板的配置文件（``config.json``文件）

        :param str mcp_id: MCP模板ID
        :param MCPConfig config: MCP配置
        :return: 无
        """
        config_path = MCP_PATH / "template" / mcp_id / "config.json"
        await Path.mkdir(config_path.parent, parents=True, exist_ok=True)

        f = await config_path.open("w+", encoding="utf-8")
        config_dict = config.model_dump(by_alias=True, exclude_none=True)
        await f.write(json.dumps(config_dict, indent=4, ensure_ascii=False))
        await f.aclose()


    @staticmethod
    async def get_config(mcp_id: str) -> MCPServerConfig:
        """
        获取MCP服务配置

        :param mcp_id: str: MCP服务ID
        :return: MCP服务配置
        """
        config_path = MCP_PATH / "template" / mcp_id / "config.json"
        if not await config_path.exists():
            err = f"MCP模板配置文件不存在: {mcp_id}"
            logger.error(err)
            raise FileNotFoundError(err)
        f = await config_path.open("r", encoding="utf-8")
        config = json.loads(await f.read())
        await f.aclose()
        return MCPServerConfig.model_validate(config)


    @staticmethod
    async def user_active_template(user_id: str, mcp_id: str, mcp_env: dict[str, Any] | None = None) -> None:
        """
        用户激活MCP模板

        激活MCP模板时，将已安装的环境拷贝一份到用户目录，并更新数据库

        :param str user_id: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        :raises FileExistsError: MCP模板已存在或有同名文件，无法激活
        """
        template_path = MCP_PATH / "template" / str(mcp_id)
        user_path = MCP_PATH / "users" / user_id / str(mcp_id)

        if await user_path.exists():
            err = f'MCP模板"{mcp_id}"已存在或有同名文件，无法激活'
            raise FileExistsError(err)

        mcp_config = await MCPLoader.get_config(mcp_id)
        await asyncer.asyncify(shutil.copytree)(
            template_path.as_posix(),
            user_path.as_posix(),
            dirs_exist_ok=True,
            symlinks=True,
        )

        mcpsvc = mcp_config.mcpServers[mcp_id]
        if mcp_env is not None:
            mcp_config.mcpServers[mcp_id].env.update(mcp_env)
        if mcp_config.mcpType == MCPType.STDIO and isinstance(mcpsvc, MCPServerStdioConfig):
            index = None
            for i in range(len(mcpsvc.args)):
                if mcpsvc.args[i] == "--directory":
                    index = i + 1
                    break
            if index is not None:
                if index < len(mcpsvc.args):
                    mcpsvc.args[index] = str(user_path) + "/project"
                else:
                    mcpsvc.args.append(str(user_path) + "/project")
            else:
                mcpsvc.args = ["--directory", str(user_path) + "/project", *mcpsvc.args]

        user_config_path = user_path / "config.json"
        mcp_config.mcpServers[mcp_id] = mcpsvc
        f = await user_config_path.open("w", encoding="utf-8", errors="ignore")
        await f.write(
            json.dumps(
                mcp_config.model_dump(by_alias=True, exclude_none=True),
                indent=4,
                ensure_ascii=False,
            ),
        )
        await f.aclose()
        async with postgres.session() as session:
            await session.merge(MCPActivated(
                mcpId=mcp_id,
                userId=user_id,
            ))
            await session.commit()

    @staticmethod
    async def user_deactive_template(user_id: str, mcp_id: str) -> None:
        """
        取消激活MCP模板

        取消激活MCP模板时，删除用户目录下对应的MCP环境文件夹，并更新数据库

        :param str user_id: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        user_path = MCP_PATH / "users" / user_id / str(mcp_id)
        await asyncer.asyncify(shutil.rmtree)(user_path.as_posix(), ignore_errors=True)

        async with postgres.session() as session:
            await session.execute(delete(MCPActivated).where(
                and_(
                    MCPActivated.mcpId == mcp_id,
                    MCPActivated.userId == user_id,
                ),
            ))
            await session.commit()


    @staticmethod
    async def _find_deleted_mcp() -> list[str]:
        """
        查找在文件系统中被修改和被删除的MCP

        :return: 被修改的MCP列表和被删除的MCP列表
        :rtype: tuple[list[str], list[str]]
        """
        deleted_mcp_list = []

        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo.id))).all()
            for mcp in mcp_info:
                mcp_path: Path = MCP_PATH / "template" / str(mcp)
                if not await mcp_path.exists():
                    deleted_mcp_list.append(str(mcp))
            logger.info("[MCPLoader] 这些MCP在文件系统中被删除: %s", deleted_mcp_list)
            return deleted_mcp_list


    @staticmethod
    async def cancel_installing_task(cancel_mcp_list: list[str]) -> None:
        """
        取消正在安装的MCP模板任务

        :param list[str] cancel_mcp_list: 需要取消的MCP列表
        :return: 无
        """
        async with postgres.session() as session:
            result = await session.scalars(
                select(MCPInfo).where(
                    and_(
                        MCPInfo.status == MCPInstallStatus.INSTALLING,
                        MCPInfo.id.in_(cancel_mcp_list),
                    ),
                ),
            )
            result = result.all()
            for mcp in result:
                mcp.status = MCPInstallStatus.CANCELLED
            await session.commit()

        for mcp_id in cancel_mcp_list:
            ProcessHandler.remove_task(mcp_id)
        logger.info("[MCPLoader] 取消这些正在安装的MCP模板任务: %s", cancel_mcp_list)


    @staticmethod
    async def remove_deleted_mcp(deleted_mcp_list: list[str]) -> None:
        """
        删除无效的MCP在数据库中的记录

        :param list[str] deleted_mcp_list: 被删除的MCP列表
        :return: 无
        """
        async with postgres.session() as session:
            for mcp_id in deleted_mcp_list:
                mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_id))).one_or_none()
                if not mcp_info:
                    continue

                mcp_activated = (await session.scalars(select(MCPActivated).where(MCPActivated.mcpId == mcp_id))).all()
                for activated in mcp_activated:
                    await MCPLoader.user_deactive_template(activated.userId, mcp_id)
                    await session.delete(activated)
                await session.delete(mcp_info)
            await session.commit()
            logger.info("[MCPLoader] 清除数据库中无效的MCP")

        async with postgres.session() as session:
            for mcp_id in deleted_mcp_list:
                await session.execute(
                    delete(embedding.MCPVector).where(embedding.MCPVector.id == mcp_id),
                )
                await session.execute(
                    delete(embedding.MCPToolVector).where(embedding.MCPToolVector.mcpId == mcp_id),
                )
            await session.commit()
            logger.info("[MCPLoader] 清除数据库中无效的MCP向量化数据")


    @staticmethod
    async def update_template_status(mcp_id: str, status: MCPInstallStatus, pg: Postgres = postgres) -> None:
        """
        更新数据库中MCP模板状态

        :param str mcp_id: MCP模板ID
        :param MCPInstallStatus status: MCP模板状态
        :param Postgres pg: PostgreSQL实例，默认为全局单例postgres
        :return: 无
        """
        async with pg.session() as session:
            mcp_data = (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_id))).one_or_none()
            if mcp_data:
                logger.info("[MCPLoader] 更新MCP模板状态: %s -> %s", mcp_id, status)
                mcp_data.status = status
                await session.merge(mcp_data)
                await session.commit()


    @staticmethod
    async def delete_mcp(mcp_id: str) -> None:
        """
        删除MCP

        :param str mcp_id: 被删除的MCP ID
        :return: 无
        """
        await MCPLoader.remove_deleted_mcp([mcp_id])
        template_path = MCP_PATH / "template" / str(mcp_id)
        if await template_path.exists():
            await asyncer.asyncify(shutil.rmtree)(template_path.as_posix(), ignore_errors=True)


    @staticmethod
    async def _load_user_mcp() -> None:
        """
        加载用户MCP

        :return: 用户MCP列表
        :rtype: dict[str, list[str]]
        """
        user_path = MCP_PATH / "users"
        if not await user_path.exists():
            logger.warning("[MCPLoader] users目录不存在，跳过加载用户MCP")
            return

        mcp_list = {}
        async with postgres.session() as session:
            async for user_dir in user_path.iterdir():
                if not await user_dir.is_dir():
                    continue

                async for mcp_dir in user_dir.iterdir():
                    mcp_item = (
                        await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_dir.name))
                    ).one()
                    if not mcp_item:
                        await asyncer.asyncify(shutil.rmtree)(mcp_dir.as_posix(), ignore_errors=True)
                        continue

                    if mcp_dir.name not in mcp_list:
                        mcp_list[mcp_dir.name] = []
                    mcp_list[mcp_dir.name].append(user_dir.name)

        async with postgres.session() as session:
            for mcp_id, user_list in mcp_list.items():
                await session.execute(delete(MCPActivated).where(MCPActivated.mcpId == mcp_id))
                for user_id in user_list:
                    session.add(MCPActivated(
                        mcpId=mcp_id,
                        userId=user_id,
                    ))
            await session.commit()


    @staticmethod
    async def set_vector() -> None:
        """
        将MCP工具描述进行向量化并存入数据库

        :return: 无
        """
        try:
            mcp_configs = await MCPLoader._get_all_mcp_configs()

            for mcp_id, config in mcp_configs.items():
                try:
                    tool_list = await MCPLoader._get_template_tool(mcp_id, config)
                    await MCPLoader._handle_tool_vectorization(mcp_id, config, tool_list, postgres)
                    logger.info("[MCPLoader] MCP工具向量化完成: %s", mcp_id)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[MCPLoader] MCP工具向量化失败: %s, 错误: %s", mcp_id, str(e))
                    continue

            logger.info("[MCPLoader] 所有MCP工具向量化完成")
        except Exception as e:
            err = "[MCPLoader] MCP工具向量化失败"
            logger.exception(err)
            raise RuntimeError(err) from e

    @staticmethod
    async def init() -> None:
        """
        初始化MCP加载器

        :return: 无
        """
        deleted_mcp_list = await MCPLoader._find_deleted_mcp()
        await MCPLoader.remove_deleted_mcp(deleted_mcp_list)

        await MCPLoader._check_dir()

        await MCPLoader._init_all_template()
        await MCPLoader.cancel_all_installing_task()

        await MCPLoader._load_user_mcp()
