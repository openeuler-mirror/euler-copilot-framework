# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow加载器"""

import asyncio
import logging
from hashlib import sha256
from typing import Any

import aiofiles
import yaml
from anyio import Path

from apps.common.config import Config
from apps.schemas.enum_var import NodeType,EdgeType
from apps.schemas.flow import AppFlow, Flow
from apps.schemas.pool import AppPool
from apps.models.vector import FlowPoolVector
from apps.llm.embedding import Embedding
from apps.services.node import NodeManager
from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB
from apps.scheduler.util import yaml_enum_presenter, yaml_str_presenter

logger = logging.getLogger(__name__)
BASE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "app"

class FlowLoader:
    """工作流加载器"""

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

    async def _process_edges(self, flow_yaml: dict[str, Any], flow_id: str, app_id: str) -> dict[str, Any]:
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

    async def _process_steps(self, flow_yaml: dict[str, Any], flow_id: str, app_id: str) -> dict[str, Any]:
        """处理工作流步骤的转换"""
        logger.info("[FlowLoader] 应用 %s：解析工作流 %s 的步骤", flow_id, app_id)
        for key, step in flow_yaml["steps"].items():
            if key[0] == "_":
                err = f"[FlowLoader] 步骤名称不能以下划线开头：{key}"
                logger.error(err)
                raise ValueError(err)
            if step["type"]==NodeType.START.value or step["type"]==NodeType.END.value:
                continue
            try:
                step["type"] = await NodeManager.get_node_call_id(step["node"])
            except ValueError as e:
                logger.warning("[FlowLoader] 获取节点call_id失败：%s，错误信息：%s", step["node"], e)
                step["type"] = "Empty"
            step["name"] = (
                (await NodeManager.get_node_name(step["node"]))
                if "name" not in step or step["name"] == ""
                else step["name"]
            )
        return flow_yaml

    async def load(self, app_id: str, flow_id: str) -> Flow | None:
        """从文件系统中加载【单个】工作流"""
        logger.info("[FlowLoader] 应用 %s：加载工作流 %s...", flow_id, app_id)

        # 构建工作流文件路径
        flow_path = BASE_PATH / app_id / "flow" / f"{flow_id}.yaml"
        if not await flow_path.exists():
            logger.error("[FlowLoader] 应用 %s：工作流文件 %s 不存在", app_id, flow_path)
            return None

        try:
            # 加载YAML文件
            flow_yaml = await self._load_yaml_file(flow_path)
            if not flow_yaml:
                return None

            # 按顺序处理工作流配置
            for processor in [
                lambda y: self._validate_basic_fields(y, flow_path),
                lambda y: self._process_edges(y, flow_id, app_id),
                lambda y: self._process_steps(y, flow_id, app_id),
            ]:
                flow_yaml = await processor(flow_yaml)
                if not flow_yaml:
                    return None
            flow_config = Flow.model_validate(flow_yaml)
            await self._update_db(
                app_id,
                AppFlow(
                    id=flow_id,
                    name=flow_config.name,
                    description=flow_config.description,
                    enabled=True,
                    path=str(flow_path),
                    debug=flow_config.debug,
                ),
            )
            return Flow.model_validate(flow_yaml)
        except Exception:
            logger.exception("[FlowLoader] 应用 %s：工作流 %s 格式不合法", app_id, flow_id)
            return None

    async def save(self, app_id: str, flow_id: str, flow: Flow) -> None:
        """保存工作流"""
        flow_path = BASE_PATH / app_id / "flow" / f"{flow_id}.yaml"
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
            AppFlow(
                id=flow_id,
                name=flow.name,
                description=flow.description,
                enabled=True,
                path=str(flow_path),
                debug=flow.debug,
            ),
        )

    async def delete(self, app_id: str, flow_id: str) -> bool:
        """删除指定工作流文件"""
        flow_path = BASE_PATH / app_id / "flow" / f"{flow_id}.yaml"
        # 确保目标为文件且存在
        if await flow_path.exists():
            try:
                await flow_path.unlink()
                logger.info("[FlowLoader] 成功删除工作流文件：%s", flow_path)
            except Exception:
                logger.exception("[FlowLoader] 删除工作流文件失败：%s", flow_path)
                return False

            table = await LanceDB().get_table("flow")
            try:
                await table.delete(f"id = '{flow_id}'")
            except Exception:
                logger.exception("[FlowLoader] LanceDB删除flow失败")
            return True
        logger.warning("[FlowLoader] 工作流文件不存在或不是文件：%s", flow_path)
        return True

    async def _update_db(self, app_id: str, metadata: AppFlow) -> None:  # noqa: C901
        """更新数据库"""
        try:
            app_collection = MongoDB().get_collection("app")
            # 获取当前的flows
            app_data = await app_collection.find_one({"_id": app_id})
            if not app_data:
                err = f"[FlowLoader] App {app_id} 不存在"
                logger.error(err)
                return
            app_obj = AppPool.model_validate(app_data)
            flows = app_obj.flows

            for flow in flows:
                if flow.id == metadata.id:
                    flows.remove(flow)
                    break
            flows.append(metadata)

            # 执行更新操作
            await app_collection.update_one(
                filter={
                    "_id": app_id,
                },
                update={
                    "$set": {
                        "flows": [flow.model_dump(by_alias=True, exclude_none=True) for flow in flows],
                    },
                },
                upsert=True,
            )
            flow_path = BASE_PATH / app_id / "flow" / f"{metadata.id}.yaml"
            async with aiofiles.open(flow_path, "rb") as f:
                new_hash = sha256(await f.read()).hexdigest()

            key = f"hashes.flow/{metadata.id}.yaml"
            await app_collection.aggregate(
                [
                    {"$match": {"_id": app_id}},
                    {"$replaceWith": {"$setField": {"field": key, "input": "$$ROOT", "value": new_hash}}},
                ],
            )
        except Exception:
            logger.exception("[FlowLoader] 更新 MongoDB 失败")

        # 删除重复的ID
        while True:
            try:
                table = await LanceDB().get_table("flow")
                await table.delete(f"id = '{metadata.id}'")
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[FlowLoader] LanceDB删除flow冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise
        # 进行向量化
        service_embedding = await Embedding.get_embedding([metadata.description])
        vector_data = [
            FlowPoolVector(
                id=metadata.id,
                app_id=app_id,
                embedding=service_embedding[0],
            ),
        ]
        while True:
            try:
                table = await LanceDB().get_table("flow")
                await table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                    vector_data,
                )
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[FlowLoader] LanceDB插入flow冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise
