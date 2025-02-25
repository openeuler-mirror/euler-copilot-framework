"""App加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import ray
from anyio import Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from apps.common.config import config
from apps.constants import APP_DIR, FLOW_DIR, LOGGER
from apps.entities.flow import AppFlow, AppMetadata, MetadataType, Permission
from apps.entities.pool import AppPool
from apps.entities.vector import AppPoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.pool.loader.metadata import MetadataLoader


@ray.remote
class AppLoader:
    """应用加载器"""

    async def load(self, app_id: str, hashes: dict[str, str]) -> None:
        """从文件系统中加载应用

        :param app_id: 应用 ID
        """
        app_path = Path(config["SEMANTICS_DIR"]) / APP_DIR / app_id
        metadata_path = app_path / "metadata.yaml"
        metadata = await MetadataLoader().load_one(metadata_path)
        if not metadata:
            err = f"元数据不存在: {metadata_path}"
            LOGGER.error(err)
            raise ValueError(err)
        metadata.hashes = hashes

        if not isinstance(metadata, AppMetadata):
            err = f"[AppLoader] 元数据类型错误: {metadata_path}"
            LOGGER.error(err)
            raise TypeError(err)

        # 加载工作流
        flow_path = app_path / FLOW_DIR
        flow_loader = FlowLoader()

        flow_ids = [app_flow.id for app_flow in metadata.flows]
        new_flows: list[AppFlow] = []
        async for flow_file in flow_path.rglob("*.yaml"):
            if flow_file.stem not in flow_ids:
                LOGGER.warning(f"[AppLoader] 工作流 {flow_file} 不在元数据中")
            flow = await flow_loader.load(app_id, flow_file.stem)
            if not flow:
                err = f"[AppLoader] 工作流 {flow_file} 加载失败"
                LOGGER.error(err)
                raise ValueError(err)
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
            err = f"[AppLoader] 元数据验证失败：{e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e
        await self._update_db(metadata)


    async def save(self, metadata: AppMetadata, app_id: str) -> None:
        """保存应用

        :param metadata: 应用元数据
        :param app_id: 应用 ID
        """
        # 创建文件夹
        app_path = Path(config["SEMANTICS_DIR"]) / APP_DIR / app_id
        if not await app_path.exists():
            await app_path.mkdir(parents=True, exist_ok=True)
        # 保存元数据
        await MetadataLoader().save_one(MetadataType.APP, metadata, app_id)
        # 重新载入
        file_checker = FileChecker()
        await file_checker.diff_one(app_path)
        await self.load(app_id, file_checker.hashes[f"{APP_DIR}/{app_id}"])

    async def delete(self, app_id: str) -> None:
        """删除App，并更新数据库

        :param app_id: 应用 ID
        """
        app_collection = MongoDB.get_collection("app")
        try:
            await app_collection.delete_one({"_id": app_id})
        except Exception as e:
            err = f"[AppLoader] 删除App失败：{e}"
            LOGGER.error(err)

        session = await PostgreSQL.get_session()
        try:
            await session.execute(delete(AppPoolVector).where(AppPoolVector.id == app_id))
            await session.commit()
        except Exception as e:
            err = f"[AppLoader] 删除数据库失败：{e}"
            LOGGER.error(err)

        await session.aclose()


    async def _update_db(self, metadata: AppMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[AppLoader] 应用 {metadata.id} 的哈希值为空"
            LOGGER.error(err)
            raise ValueError(err)
        # 更新应用数据
        try:
            app_collection = MongoDB.get_collection("app")
            await app_collection.update_one(
                {"_id": metadata.id},
                {
                    "$set": jsonable_encoder(
                        AppPool(
                            _id=metadata.id,
                            icon=metadata.icon,
                            name=metadata.name,
                            description=metadata.description,
                            author=metadata.author,
                            links=metadata.links,
                            first_questions=metadata.first_questions,
                            history_len=metadata.history_len,
                            permission=metadata.permission if metadata.permission else Permission(),
                            flows=metadata.flows,
                            hashes=metadata.hashes,
                        ),
                    ),
                },
                upsert=True,
            )
        except Exception as e:
            err = f"[AppLoader] 更新 MongoDB 失败：{e}"
            LOGGER.error(err)
            raise RuntimeError(err) from e

        # 向量化所有数据并保存
        session = await PostgreSQL.get_session()
        service_embedding = await PostgreSQL.get_embedding([metadata.description])
        insert_stmt = (
            insert(AppPoolVector)
            .values(
                id=metadata.id,
                embedding=service_embedding[0],
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"embedding": service_embedding[0]},
            )
        )
        await session.execute(insert_stmt)
        await session.commit()
        await session.aclose()
