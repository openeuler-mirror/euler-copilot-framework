# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow加载器；下属于AppLoader"""

import logging
import uuid
from hashlib import sha256
from typing import Any

import aiofiles
import yaml
from anyio import Path
from sqlalchemy import and_, delete, func, select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.llm import embedding
from apps.models import App, AppHashes
from apps.models import Flow as FlowInfo
from apps.scheduler.util import yaml_enum_presenter, yaml_str_presenter
from apps.schemas.enum_var import EdgeType, NodeType
from apps.schemas.flow import Flow
from apps.services.node import NodeManager

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "app"


class FlowLoader:
    """工作流加载器"""

    @staticmethod
    async def _load_all_flows() -> list[FlowInfo]:
        """从数据库加载所有工作流"""
        async with postgres.session() as session:
            # 查询所有工作流
            flows_query = select(FlowInfo)
            return list((await session.scalars(flows_query)).all())

    async def _load_yaml_file(self, flow_path: Path) -> dict[str, Any]:
        """从YAML文件加载工作流配置"""
        try:
            async with aiofiles.open(flow_path, encoding="utf-8") as f:
                return yaml.safe_load(await f.read())
        except Exception:
            logger.exception("[FlowLoader] 加载YAML文件失败：%s", flow_path)
            return {}


    async def _validate_basic_fields(self, flow_yaml: dict[str, Any], flow_path: Path) -> dict[str, Any]:
        """验证工作流基本字段"""
        if "name" not in flow_yaml or not flow_yaml["name"]:
            logger.error("[FlowLoader] 工作流名称不能为空：%s", flow_path)
            return {}

        if "description" not in flow_yaml or not flow_yaml["description"]:
            logger.error("[FlowLoader] 工作流描述不能为空：%s", flow_path)
            return {}

        if "start" not in flow_yaml["steps"] or "end" not in flow_yaml["steps"]:
            logger.error("[FlowLoader] 工作流必须包含开始和结束节点：%s", flow_path)
            return {}

        return flow_yaml


    async def _process_edges(self, flow_yaml: dict[str, Any], flow_id: str, app_id: uuid.UUID) -> dict[str, Any]:
        """处理工作流边的转换"""
        logger.info("[FlowLoader] 应用 %s：解析工作流 %s 的边", flow_id, app_id)
        try:
            for edge in flow_yaml["edges"]:
                if "from" in edge:
                    edge["edge_from"] = edge.pop("from")
                if "to" in edge:
                    edge["edge_to"] = edge.pop("to")
                if "type" in edge:
                    edge["edge_type"] = EdgeType[edge.pop("type").upper()]
        except Exception:
            logger.exception("[FlowLoader] 处理边时发生错误")
            return {}
        else:
            return flow_yaml


    async def _process_steps(self, flow_yaml: dict[str, Any], flow_id: str, app_id: uuid.UUID) -> dict[str, Any]:
        """处理工作流步骤的转换"""
        logger.info("[FlowLoader] 应用 %s：解析工作流 %s 的步骤", flow_id, app_id)
        for key, step in flow_yaml["steps"].items():
            if key[0] == "_":
                err = f"[FlowLoader] 步骤名称不能以下划线开头：{key}"
                logger.error(err)
                raise ValueError(err)
            if step["type"]==NodeType.START.value or step["type"]==NodeType.END.value:
                continue
            node_data = await NodeManager.get_node(step["node"])
            try:
                step["type"] = node_data.callId
            except ValueError as e:
                logger.warning("[FlowLoader] 获取节点call_id失败：%s，错误信息：%s", step["node"], e)
                step["type"] = "Empty"
            step["name"] = (
                node_data.name
                if "name" not in step or step["name"] == ""
                else step["name"]
            )
            step["description"] = (
                node_data.description
                if "description" not in step or step["description"] == ""
                else step["description"]
            )
        return flow_yaml


    async def load(self, app_id: uuid.UUID, flow_id: str) -> Flow:
        """从文件系统中加载【单个】工作流"""
        logger.info("[FlowLoader] 应用 %s：加载工作流 %s...", flow_id, app_id)

        # 构建工作流文件路径
        flow_path = BASE_PATH / str(app_id) / "flow" / f"{flow_id}.yaml"
        if not await flow_path.exists():
            err = f"[FlowLoader] 应用 {app_id}：工作流文件 {flow_path} 不存在"
            logger.error(err)
            raise FileNotFoundError(err)

        # 加载YAML文件
        flow_yaml = await self._load_yaml_file(flow_path)
        if not flow_yaml:
            err = f"[FlowLoader] 应用 {app_id}：工作流文件 {flow_path} 加载失败"
            logger.error(err)
            raise RuntimeError(err)

        # 按顺序处理工作流配置
        for processor in [
            lambda y: self._validate_basic_fields(y, flow_path),
            lambda y: self._process_edges(y, flow_id, app_id),
            lambda y: self._process_steps(y, flow_id, app_id),
        ]:
            flow_yaml = await processor(flow_yaml)
            if not flow_yaml:
                err = f"[FlowLoader] 应用 {app_id}：工作流文件 {flow_path} 格式不合法"
                logger.error(err)
                raise RuntimeError(err)

        flow_config = Flow.model_validate(flow_yaml)
        await self._update_db(
            app_id,
            FlowInfo(
                appId=app_id,
                id=flow_id,
                name=flow_config.name,
                description=flow_config.description,
                enabled=True,
                path=str(flow_path),
                debug=flow_config.checkStatus.debug,
            ),
        )
        # 重新向量化该App的所有工作流
        await self._update_vector(app_id)
        return Flow.model_validate(flow_yaml)


    async def save(self, app_id: uuid.UUID, flow_id: str, flow: Flow) -> None:
        """保存工作流"""
        flow_path = BASE_PATH / str(app_id) / "flow" / f"{flow_id}.yaml"
        if not await flow_path.parent.exists():
            await flow_path.parent.mkdir(parents=True)

        flow_dict = flow.model_dump(by_alias=True, exclude_none=True)
        async with aiofiles.open(flow_path, mode="w", encoding="utf-8") as f:
            yaml.add_representer(str, yaml_str_presenter)
            yaml.add_representer(EdgeType, yaml_enum_presenter)
            await f.write(
                yaml.dump(
                    flow_dict,
                    allow_unicode=True,
                    sort_keys=False,
                ),
            )
        await self._update_db(
            app_id,
            FlowInfo(
                appId=app_id,
                id=flow_id,
                name=flow.name,
                description=flow.description,
                enabled=True,
                path=str(flow_path),
                debug=flow.checkStatus.debug,
            ),
        )
        # 重新向量化该App的所有工作流
        await self._update_vector(app_id)


    async def delete(self, app_id: uuid.UUID, flow_id: str) -> None:
        """删除指定工作流文件"""
        flow_path = BASE_PATH / str(app_id) / "flow" / f"{flow_id}.yaml"
        # 确保目标为文件且存在
        if await flow_path.exists():
            logger.info("[FlowLoader] 删除工作流文件：%s", flow_path)
            await flow_path.unlink()

            async with postgres.session() as session:
                await session.execute(delete(FlowInfo).where(
                    and_(
                        FlowInfo.appId == app_id,
                        FlowInfo.id == flow_id,
                    ),
                ))
                await session.execute(
                    delete(embedding.FlowPoolVector).where(embedding.FlowPoolVector.id == flow_id),
                )
                await session.commit()
                return
        logger.warning("[FlowLoader] 工作流文件不存在或不是文件：%s", flow_path)


    async def _update_db(self, app_id: uuid.UUID, metadata: FlowInfo) -> None:
        """更新数据库"""
        # 检查App是否存在
        async with postgres.session() as session:
            app_num = (await session.scalars(
                select(func.count(App.id)).where(App.id == app_id),
            )).one()
            if app_num == 0:
                err = f"[FlowLoader] App {app_id} 不存在"
                logger.error(err)
                return

            # 删除旧的Flow数据
            await session.execute(delete(FlowInfo).where(FlowInfo.appId == app_id))
            await session.execute(delete(AppHashes).where(
                and_(
                    AppHashes.appId == app_id,
                    AppHashes.filePath == f"flow/{metadata.id}.yaml",
                ),
            ))

            # 创建新的Flow数据
            session.add(metadata)

            flow_path = BASE_PATH / str(app_id) / "flow" / f"{metadata.id}.yaml"
            async with aiofiles.open(flow_path, "rb") as f:
                new_hash = sha256(await f.read()).hexdigest()

            flow_hash = AppHashes(
                appId=app_id,
                hash=new_hash,
                filePath=f"flow/{metadata.id}.yaml",
            )
            session.add(flow_hash)
            await session.commit()

    async def _update_vector(self, app_id: uuid.UUID) -> None:
        """重新向量化指定App的所有工作流"""
        # 从数据库加载该App的所有工作流
        async with postgres.session() as session:
            flows_query = select(FlowInfo).where(FlowInfo.appId == app_id)
            flows = list((await session.scalars(flows_query)).all())

        if not flows:
            logger.warning("[FlowLoader] App %s 没有工作流，跳过向量化", app_id)
            return

        # 获取所有工作流的描述并生成向量
        flow_descriptions = [flow.description for flow in flows]
        flow_vecs = await embedding.get_embedding(flow_descriptions)

        async with postgres.session() as session:
            # 删除该App的所有旧向量数据
            await session.execute(
                delete(embedding.FlowPoolVector).where(embedding.FlowPoolVector.appId == app_id),
            )

            # 插入新的向量数据
            for flow, vec in zip(flows, flow_vecs, strict=True):
                session.add(embedding.FlowPoolVector(
                    id=flow.id,
                    appId=app_id,
                    embedding=vec,
                ))
            await session.commit()

    @staticmethod
    async def set_vector() -> None:
        """将所有工作流的向量化数据存入数据库"""
        flows = await FlowLoader._load_all_flows()

        # 为每个工作流更新向量数据
        for flow in flows:
            flow_vecs = await embedding.get_embedding([flow.description])

            async with postgres.session() as session:
                # 删除旧数据
                await session.execute(
                    delete(embedding.FlowPoolVector).where(embedding.FlowPoolVector.id == flow.id),
                )
                # 插入新数据
                session.add(embedding.FlowPoolVector(
                    id=flow.id,
                    appId=flow.appId,
                    embedding=flow_vecs[0],
                ))
                await session.commit()
