# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""App加载器"""

import logging
import shutil

from anyio import Path
from fastapi.encoders import jsonable_encoder

from apps.common.config import Config
from apps.schemas.agent import AgentAppMetadata
from apps.schemas.enum_var import AppType
from apps.schemas.flow import AppFlow, AppMetadata, MetadataType, Permission
from apps.schemas.pool import AppPool
from apps.common.mongo import MongoDB
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.pool.loader.metadata import MetadataLoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "app"


class AppLoader:
    """应用加载器"""

    async def load(self, app_id: str, hashes: dict[str, str]) -> None:  # noqa: C901
        """
        从文件系统中加载应用

        :param app_id: 应用 ID
        """
        app_path = BASE_PATH / app_id
        metadata_path = app_path / "metadata.yaml"
        metadata = await MetadataLoader().load_one(metadata_path)
        if not metadata:
            err = f"[AppLoader] 元数据不存在: {metadata_path}"
            raise ValueError(err)
        metadata.hashes = hashes

        if not isinstance(metadata, (AppMetadata, AgentAppMetadata)):
            err = f"[AppLoader] 元数据类型错误: {metadata_path}"
            raise TypeError(err)

        if metadata.app_type == AppType.FLOW and isinstance(metadata, AppMetadata):
            # 加载工作流
            flow_path = app_path / "flow"
            flow_loader = FlowLoader()

            flow_ids = [app_flow.id for app_flow in metadata.flows]
            new_flows: list[AppFlow] = []
            async for flow_file in flow_path.rglob("*.yaml"):
                if flow_file.stem not in flow_ids:
                    logger.warning("[AppLoader] 工作流 %s 不在元数据中", flow_file)
                flow = await flow_loader.load(app_id, flow_file.stem)
                if not flow:
                    err = f"[AppLoader] 工作流 {flow_file} 加载失败"
                    raise ValueError(err)
                if not flow.debug:
                    metadata.published = False
                new_flows.append(
                    AppFlow(
                        id=flow_file.stem,
                        name=flow.name,
                        description=flow.description,
                        path=flow_file.as_posix(),
                        debug=flow.debug,
                    ),
                )
            metadata.flows = new_flows
            try:
                metadata = AppMetadata.model_validate(metadata)
            except Exception as e:
                err = "[AppLoader] Flow应用元数据验证失败"
                logger.exception(err)
                raise RuntimeError(err) from e
        elif metadata.app_type == AppType.AGENT and isinstance(metadata, AgentAppMetadata):
            # 加载模型
            try:
                metadata = AgentAppMetadata.model_validate(metadata)
            except Exception as e:
                err = "[AppLoader] Agent应用元数据验证失败"
                logger.exception(err)
                raise RuntimeError(err) from e
        await self._update_db(metadata)

    async def save(self, metadata: AppMetadata | AgentAppMetadata, app_id: str) -> None:
        """
        保存应用

        :param metadata: 应用元数据
        :param app_id: 应用 ID
        """
        # 创建文件夹
        app_path = BASE_PATH / app_id
        if not await app_path.exists():
            await app_path.mkdir(parents=True, exist_ok=True)
        # 保存元数据
        await MetadataLoader().save_one(MetadataType.APP, metadata, app_id)
        # 重新载入
        file_checker = FileChecker()
        await file_checker.diff_one(app_path)
        await self.load(app_id, file_checker.hashes[f"app/{app_id}"])

    @staticmethod
    async def delete(app_id: str, *, is_reload: bool = False) -> None:
        """
        删除App，并更新数据库

        :param app_id: 应用 ID
        """
        mongo = MongoDB()
        try:
            app_collection = mongo.get_collection("app")
            await app_collection.delete_one({"_id": app_id})  # 删除应用数据
            user_collection = mongo.get_collection("user")
            # 删除用户使用记录
            await user_collection.update_many(
                {f"app_usage.{app_id}": {"$exists": True}},
                {"$unset": {f"app_usage.{app_id}": ""}},
            )
            # 删除用户收藏
            await user_collection.update_many(
                {"fav_apps": {"$in": [app_id]}},
                {"$pull": {"fav_apps": app_id}},
            )
        except Exception:
            logger.exception("[AppLoader] MongoDB删除App失败")

        if not is_reload:
            app_path = BASE_PATH / app_id
            if await app_path.exists():
                shutil.rmtree(str(app_path), ignore_errors=True)

    @staticmethod
    async def _update_db(metadata: AppMetadata | AgentAppMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[AppLoader] 应用 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)
        # 更新应用数据
        mongo = MongoDB()
        try:
            app_collection = mongo.get_collection("app")
            metadata.permission = metadata.permission if metadata.permission else Permission()
            await app_collection.update_one(
                {"_id": metadata.id},
                {
                    "$set": jsonable_encoder(
                        AppPool(
                            _id=metadata.id,
                            **(metadata.model_dump(by_alias=True)),
                        ),
                    ),
                },
                upsert=True,
            )
            app_pool = await app_collection.find_one({"_id": metadata.id})
        except Exception:
            logger.exception("[AppLoader] 更新 MongoDB 失败")
