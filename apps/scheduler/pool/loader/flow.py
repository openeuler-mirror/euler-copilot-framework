"""Flow加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import logging
from typing import Optional

import aiofiles
import yaml
from anyio import Path

from apps.common.config import config
from apps.constants import APP_DIR, FLOW_DIR
from apps.entities.enum_var import EdgeType
from apps.entities.flow import Flow
from apps.manager.node import NodeManager

logger = logging.getLogger(__name__)

class FlowLoader:
    """工作流加载器"""

    async def load(self, app_id: str, flow_id: str) -> Optional[Flow]:
        """从文件系统中加载【单个】工作流"""
        logger.info("[FlowLoader] 加载工作流 %s 应用 %s...", flow_id, app_id)
        flow_path = Path(config["SEMANTICS_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"
        async with aiofiles.open(flow_path, encoding="utf-8") as f:
            flow_yaml = yaml.safe_load(await f.read())

        if "name" not in flow_yaml or not flow_yaml["name"]:
            err = f"工作流名称不能为空：{flow_path!s}"
            logger.error(err)
            return None

        if "description" not in flow_yaml or not flow_yaml["description"]:
            err = f"工作流描述不能为空：{flow_path!s}"
            logger.error(err)
            return None

        if "start" not in flow_yaml["steps"] or "end" not in flow_yaml["steps"]:
            err = f"工作流必须包含开始和结束节点：{flow_path!s}"
            logger.error(err)
            raise ValueError(err)

        logger.info("[FlowLoader] 解析工作流 %s 应用 %s 的边...", flow_id, app_id)
        for edge in flow_yaml["edges"]:
            # 把from变成edge_from,to改成edge_to，type改成edge_type
            if "from" in edge:
                edge["edge_from"] = edge.pop("from")
            if "to" in edge:
                edge["edge_to"] = edge.pop("to")
            if "type" in edge:
                # 将 type 转换为 EdgeType 枚举类型
                try:
                    edge["edge_type"] = EdgeType[edge.pop("type").upper()]
                except KeyError as e:
                    err = f"Invalid edge type {edge['type']}"
                    logger.exception(err)
                    raise ValueError(err) from e

        logger.info("[FlowLoader] 解析工作流 %s 应用 %s 的步骤...", flow_id, app_id)
        for key, step in flow_yaml["steps"].items():
            if key == "start":
                step["name"] = "开始"
                step["description"] = "开始节点"
                step["type"] = "start"
            elif key == "end":
                step["name"] = "结束"
                step["description"] = "结束节点"
                step["type"] = "end"
            else:
                step["type"] = await NodeManager.get_node_call_id(step["node"])
                step["name"] = (
                    await NodeManager.get_node_name(step["node"])
                    if "name" not in step or step["name"] == ""
                    else step["name"]
                )

        logger.info("[FlowLoader] 验证工作流 %s 应用 %s...", flow_id, app_id)
        try:
            # 检查Flow格式，并转换为Flow对象
            return Flow.model_validate(flow_yaml)
        except Exception:
            logger.exception("[FlowLoader] 工作流 %s 应用 %s 格式不合法", flow_id, app_id)
            return None

    async def save(self, app_id: str, flow_id: str, flow: Flow) -> None:
        """保存工作流"""
        flow_path = Path(config["SEMANTICS_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"
        if not await flow_path.parent.exists():
            await flow_path.parent.mkdir(parents=True)

        flow_dict = {
            "name": flow.name,
            "description": flow.description,
            "on_error": flow.on_error.model_dump(by_alias=True, exclude_none=True),
            "steps": {
                step_id: {
                    "name": step.name,
                    "description": step.description,
                    "node": step.node,
                    "params": step.params,
                    "pos": {
                        "x": step.pos.x,
                        "y": step.pos.y,
                    },
                }
                for step_id, step in flow.steps.items()
            },
            "edges": [
                {
                    "id": edge.id,
                    "from": edge.edge_from,
                    "to": edge.edge_to,
                    "type": edge.edge_type.value if edge.edge_type else None,
                }
                for edge in flow.edges
            ],
            "debug": flow.debug,
        }

        async with aiofiles.open(flow_path, mode="w", encoding="utf-8") as f:
            await f.write(yaml.dump(flow_dict, allow_unicode=True, sort_keys=False))

    async def delete(self, app_id: str, flow_id: str) -> bool:
        """删除指定工作流文件"""
        flow_path = Path(config["SEMANTICS_DIR"]) / APP_DIR / app_id / FLOW_DIR / f"{flow_id}.yaml"
        # 确保目标为文件且存在
        if await flow_path.exists():
            try:
                await flow_path.unlink()
                logger.info("[FlowLoader] 成功删除工作流文件：%s", flow_path)
                return True
            except OSError:
                logger.exception("[FlowLoader] 删除工作流文件失败：%s", flow_path)
                return False
        else:
            logger.warning("[FlowLoader] 工作流文件不存在或不是文件：%s", flow_path)
            return True
