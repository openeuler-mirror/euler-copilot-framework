# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 加载器"""

import asyncio
import base64
import json
import logging
import random
import shutil

import asyncer
from anyio import Path
from sqids.sqids import Sqids

from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB
from apps.common.process_handler import ProcessHandler
from apps.common.singleton import SingletonMeta
from apps.constants import MCP_PATH
from apps.llm.embedding import Embedding
from apps.scheduler.pool.mcp.client import MCPClient
from apps.scheduler.pool.mcp.install import install_npx, install_uvx
from apps.schemas.mcp import (
    MCPCollection,
    MCPInstallStatus,
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPTool,
    MCPToolVector,
    MCPType,
    MCPVector,
)

logger = logging.getLogger(__name__)
sqids = Sqids(min_length=12)


class MCPLoader(metaclass=SingletonMeta):
    """
    MCP加载模块

    创建MCP Client，启动MCP进程，并将MCP基本信息（名称、描述、工具列表等）写入数据库
    """

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
    async def _install_template_task(
        mcp_id: str, config: MCPServerConfig,
    ) -> None:
        """
        安装依赖；此函数在子进程中运行

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig config: MCP配置
        :return: 无
        """
        if not config.config.auto_install:
            print(f"[Installer] MCP模板无需安装: {mcp_id}")  # noqa: T201

        elif isinstance(config.config, MCPServerStdioConfig):
            print(f"[Installer] Stdio方式的MCP模板，开始自动安装: {mcp_id}")  # noqa: T201
            if "uv" in config.config.command:
                new_config = await install_uvx(mcp_id, config.config)
            elif "npx" in config.config.command:
                new_config = await install_npx(mcp_id, config.config)

            if new_config is None:
                logger.error("[MCPLoader] MCP模板安装失败: %s", mcp_id)
                await MCPLoader.update_template_status(mcp_id, MCPInstallStatus.FAILED)
                return

            config.config = new_config

            # 重新保存config
            template_config = MCP_PATH / "template" / mcp_id / "config.json"
            f = await template_config.open("w+", encoding="utf-8")
            config_data = config.model_dump(by_alias=True, exclude_none=True)
            await f.write(json.dumps(config_data, indent=4, ensure_ascii=False))
            await f.aclose()

        else:
            print(f"[Installer] SSE/StreamableHTTP方式的MCP模板，无需安装: {mcp_id}")  # noqa: T201
            config.config.auto_install = False

        print(f"[Installer] MCP模板安装成功: {mcp_id}")  # noqa: T201
        await MCPLoader.update_template_status(mcp_id, MCPInstallStatus.READY)
        await MCPLoader._insert_template_tool(mcp_id, config)

    @staticmethod
    async def init_one_template(mcp_id: str, config: MCPServerConfig) -> None:
        """
        初始化单个MCP模板

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig config: MCP配置
        :return: 无
        """
        # 删除完成或者失败的MCP安装任务
        mcp_collection = MongoDB().get_collection("mcp")
        mcp_ids = ProcessHandler.get_all_task_ids()
        # 检索_id在mcp_ids且状态为ready或者failed的MCP的内容
        db_service_list = await mcp_collection.find(
            {"_id": {"$in": mcp_ids}, "status": {"$in": [MCPInstallStatus.READY, MCPInstallStatus.FAILED]}},
        ).to_list(None)
        for db_service in db_service_list:
            try:
                item = MCPCollection.model_validate(db_service)
            except Exception as e:
                logger.error("[MCPLoader] MCP模板数据验证失败: %s, 错误: %s", db_service["_id"], e)
                continue
            ProcessHandler.remove_task(item.id)
            logger.info("[MCPLoader] 删除已完成或失败的MCP安装进程: %s", item.id)
        # 插入数据库；这里用旧的config就可以
        await MCPLoader._insert_template_db(mcp_id, config)

        # 检查目录
        template_path = MCP_PATH / "template" / mcp_id
        await Path.mkdir(template_path, parents=True, exist_ok=True)
        # 安装MCP模板
        if not ProcessHandler.add_task(mcp_id, MCPLoader._install_template_task, mcp_id, config):
            err = f"安装任务无法执行，请稍后重试: {mcp_id}"
            logger.error(err)
            raise RuntimeError(err)

    @staticmethod
    async def _init_all_template() -> None:
        """
        初始化所有MCP模板

        遍历 ``template`` 目录下的所有MCP模板，并初始化。在Framework启动时进行此流程，确保所有MCP均可正常使用。
        这一过程会与数据库内的条目进行对比，若发生修改，则重新创建数据库条目。
        """
        template_path = MCP_PATH / "template"
        logger.info("[MCPLoader] 初始化所有MCP模板: %s", template_path)

        # 遍历所有模板
        async for mcp_dir in template_path.iterdir():
            # 不是目录
            if not await mcp_dir.is_dir():
                logger.warning("[MCPLoader] 跳过非目录: %s", mcp_dir.as_posix())
                continue

            # 检查配置文件是否存在
            config_path = mcp_dir / "config.json"
            if not await config_path.exists():
                logger.warning("[MCPLoader] 跳过没有配置文件的MCP模板: %s", mcp_dir.as_posix())
                continue

            # 读取配置并加载
            config = await MCPLoader._load_config(config_path)

            # 初始化第一个MCP Server
            logger.info("[MCPLoader] 初始化MCP模板: %s", mcp_dir.as_posix())
            await MCPLoader.init_one_template(mcp_dir.name, config)

    @staticmethod
    async def _get_template_tool(
            mcp_id: str,
            config: MCPServerConfig,
            user_sub: str | None = None,
    ) -> list[MCPTool]:
        """
        获取MCP模板的工具列表

        :param str mcp_id: MCP模板ID
        :param MCPServerConfig config: MCP配置
        :param str | None user_sub: 用户ID,默认为None
        :return: 工具列表
        :rtype: list[str]
        """
        # 创建客户端
        if (
            (config.type == MCPType.STDIO and isinstance(config.config, MCPServerStdioConfig))
            or (config.type == MCPType.SSE and isinstance(config.config, MCPServerSSEConfig))
        ):
            client = MCPClient()
        else:
            err = f"MCP {mcp_id}：未知的MCP服务类型“{config.type}”"
            logger.error(err)
            raise ValueError(err)

        await client.init(user_sub, mcp_id, config.config)

        # 获取工具列表
        tool_list = []
        for item in client.tools:
            tool_list += [MCPTool(
                id=sqids.encode([random.randint(0, 1000000) for _ in range(5)])[:6],  # noqa: S311
                name=item.name,
                mcp_id=mcp_id,
                description=item.description or "",
                input_schema=item.inputSchema,
            )]
        await client.stop()
        return tool_list

    @staticmethod
    async def _insert_template_db(mcp_id: str, config: MCPServerConfig) -> None:
        """插入单个MCP Server模板信息到数据库"""
        mcp_collection = MongoDB().get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {
                "$set": MCPCollection(
                    _id=mcp_id,
                    name=config.name,
                    description=config.description,
                    type=config.type,
                    author=config.author,
                ).model_dump(by_alias=True, exclude_none=True),
            },
            upsert=True,
        )

    @staticmethod
    async def _insert_template_tool(mcp_id: str, config: MCPServerConfig) -> None:
        """
        插入单个MCP Server模板信息到数据库

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: 无
        """
        # 获取工具列表
        tool_list = await MCPLoader._get_template_tool(mcp_id, config)

        # 基本信息插入数据库
        mcp_collection = MongoDB().get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {
                "$set": {
                    "tools": [tool.model_dump(by_alias=True, exclude_none=True) for tool in tool_list],
                },
            },
            upsert=True,
        )

        # 服务本身向量化
        embedding = await Embedding.get_embedding([config.description])

        while True:
            try:
                mcp_table = await LanceDB().get_table("mcp")
                await mcp_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute([
                    MCPVector(
                        id=mcp_id,
                        embedding=embedding[0],
                    ),
                ])
                break
            except Exception as e:
                if "Commit conflict" in str(e):
                    logger.error("[MCPLoader] LanceDB插入mcp冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

        # 工具向量化
        tool_desc_list = [tool.description for tool in tool_list]
        tool_embedding = await Embedding.get_embedding(tool_desc_list)
        for tool, embedding in zip(tool_list, tool_embedding, strict=True):
            while True:
                try:
                    mcp_tool_table = await LanceDB().get_table("mcp_tool")
                    await mcp_tool_table.merge_insert(
                        "id",
                    ).when_matched_update_all().when_not_matched_insert_all().execute([
                        MCPToolVector(
                            id=tool.id,
                            mcp_id=mcp_id,
                            embedding=embedding,
                        ),
                    ])
                    break
                except Exception as e:
                    if "Commit conflict" in str(e):
                        logger.error("[MCPLoader] LanceDB插入mcp_tool冲突，重试中...")  # noqa: TRY400
                        await asyncio.sleep(0.01)
                    else:
                        raise
        await LanceDB().create_index("mcp_tool")

    @staticmethod
    async def save_one(mcp_id: str, config: MCPServerConfig) -> None:
        """
        保存单个MCP模板的配置文件（``config.json``文件和``icon.png``文件）

        :param str mcp_id: MCP模板ID
        :param str icon: MCP模板图标
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
    async def get_icon(mcp_id: str) -> str:
        """
        获取MCP模板的图标

        :param str mcp_id: MCP模板ID
        :return: 图标
        :rtype: str
        """
        icon_path = MCP_PATH / "template" / mcp_id / "icon.png"
        if not await icon_path.exists():
            logger.warning("[MCPLoader] MCP模板图标不存在: %s", mcp_id)
            return ""
        f = await icon_path.open("rb")
        icon = await f.read()
        await f.aclose()
        return base64.b64encode(icon).decode("utf-8")

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
    async def update_template_status(mcp_id: str, status: MCPInstallStatus) -> None:
        """
        更新数据库中MCP模板状态

        :param str mcp_id: MCP模板ID
        :param MCPStatus status: MCP模板status
        :return: 无
        """
        # 更新数据库
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$set": {"status": status}},
            upsert=True,
        )

    @staticmethod
    async def user_active_template(user_sub: str, mcp_id: str) -> None:
        """
        用户激活MCP模板

        激活MCP模板时，将已安装的环境拷贝一份到用户目录，并更新数据库

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        :raises FileExistsError: MCP模板已存在或有同名文件，无法激活
        """
        template_path = MCP_PATH / "template" / mcp_id
        user_path = MCP_PATH / "users" / user_sub / mcp_id

        # 判断是否存在
        if await user_path.exists():
            err = f"MCP模板“{mcp_id}”已存在或有同名文件，无法激活"
            raise FileExistsError(err)

        # 拷贝文件
        await asyncer.asyncify(shutil.copytree)(
            template_path.as_posix(),
            user_path.as_posix(),
            dirs_exist_ok=True,
            symlinks=True,
        )

        # 更新数据库
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$addToSet": {"activated": user_sub}},
        )

    @staticmethod
    async def user_deactive_template(user_sub: str, mcp_id: str) -> None:
        """
        取消激活MCP模板

        取消激活MCP模板时，删除用户目录下对应的MCP环境文件夹，并更新数据库

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        # 删除用户目录
        user_path = MCP_PATH / "users" / user_sub / mcp_id
        await asyncer.asyncify(shutil.rmtree)(user_path.as_posix(), ignore_errors=True)

        # 更新数据库
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$pull": {"activated": user_sub}},
        )

    @staticmethod
    async def _find_deleted_mcp() -> list[str]:
        """
        查找在文件系统中被修改和被删除的MCP

        :return: 被修改的MCP列表和被删除的MCP列表
        :rtype: tuple[list[str], list[str]]
        """
        deleted_mcp_list = []

        mcp_collection = MongoDB().get_collection("mcp")
        mcp_list = await mcp_collection.find({}, {"_id": 1}).to_list(None)
        for db_item in mcp_list:
            mcp_path: Path = MCP_PATH / "template" / db_item["_id"]
            if not await mcp_path.exists():
                deleted_mcp_list.append(db_item["_id"])
        logger.info("[MCPLoader] 这些MCP在文件系统中被删除: %s", deleted_mcp_list)
        return deleted_mcp_list

    @staticmethod
    async def remove_deleted_mcp(deleted_mcp_list: list[str]) -> None:
        """
        删除无效的MCP在数据库中的记录

        :param list[str] deleted_mcp_list: 被删除的MCP列表
        :return: 无
        """
        # 从MongoDB中移除
        mcp_collection = MongoDB().get_collection("mcp")
        mcp_service_list = await mcp_collection.find(
            {"_id": {"$in": deleted_mcp_list}},
        ).to_list(None)
        for mcp_service in mcp_service_list:
            item = MCPCollection.model_validate(mcp_service)
            ProcessHandler.remove_task(item.id)
            for user_sub in item.activated:
                await MCPLoader.user_deactive_template(user_sub=user_sub, mcp_id=item.id)
        await mcp_collection.delete_many({"_id": {"$in": deleted_mcp_list}})
        logger.info("[MCPLoader] 清除数据库中无效的MCP")

        # 从LanceDB中移除
        for mcp_id in deleted_mcp_list:
            while True:
                try:
                    mcp_table = await LanceDB().get_table("mcp")
                    await mcp_table.delete(f"id == '{mcp_id}'")
                    break
                except Exception as e:
                    if "Commit conflict" in str(e):
                        logger.error("[MCPLoader] LanceDB删除mcp冲突，重试中...")  # noqa: TRY400
                        await asyncio.sleep(0.01)
                    else:
                        raise
        logger.info("[MCPLoader] 清除LanceDB中无效的MCP")

    @staticmethod
    async def delete_mcp(mcp_id: str) -> None:
        """
        删除MCP

        :param str mcp_id: 被删除的MCP ID
        :return: 无
        """
        await MCPLoader.remove_deleted_mcp([mcp_id])
        template_path = MCP_PATH / "template" / mcp_id
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

        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")

        mcp_list = {}
        # 遍历users目录
        async for user_dir in user_path.iterdir():
            if not await user_dir.is_dir():
                continue

            # 遍历单个用户的目录
            async for mcp_dir in user_dir.iterdir():
                # 检查数据库中是否有这个MCP
                mcp_item = await mcp_collection.find_one({"_id": mcp_dir.name})
                if not mcp_item:
                    # 数据库中不存在，当前文件夹无效，删除
                    await asyncer.asyncify(shutil.rmtree)(mcp_dir.as_posix(), ignore_errors=True)

                # 添加到dict
                if mcp_dir.name not in mcp_list:
                    mcp_list[mcp_dir.name] = []
                mcp_list[mcp_dir.name].append(user_dir.name)

        # 更新所有MCP的activated情况
        for mcp_id, user_list in mcp_list.items():
            await mcp_collection.update_one(
                {"_id": mcp_id},
                {"$set": {"activated": user_list}},
            )

    @staticmethod
    async def init() -> None:
        """
        初始化MCP加载器

        :return: 无
        """
        # 清空数据库
        deleted_mcp_list = await MCPLoader._find_deleted_mcp()
        await MCPLoader.remove_deleted_mcp(deleted_mcp_list)

        # 检查目录
        await MCPLoader._check_dir()

        # 初始化所有模板
        await MCPLoader._init_all_template()

        # 加载用户MCP
        await MCPLoader._load_user_mcp()
