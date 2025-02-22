"""Flow加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import asyncio
from pathlib import Path

import yaml

from apps.common.config import config
from apps.constants import LOGGER
from apps.entities.enum_var import EdgeType
from apps.entities.flow import Flow
from apps.models.mongo import MongoDB


async def search_step_type(node_id: str) -> str:
    node_collection = MongoDB.get_collection("node")
    call_collection = MongoDB.get_collection("call")
    # 查询 Node 集合获取对应的 call_id
    node_doc = await node_collection.find_one({"_id": node_id})
    if not node_doc:
        LOGGER.error(f"Node {node_id} not found")
        return None
    call_id = node_doc.get("call_id")
    if not call_id:
        LOGGER.error(f"Node {node_id} has no associated call_id")
        return None
    # 查询 Call 集合获取 node_type
    call_doc = await call_collection.find_one({"_id": call_id})
    if not call_doc:
        LOGGER.error(f"No call found with call_id: {call_id}")
        return None
    node_type = call_doc.get("type")
    if not node_type:
        LOGGER.error(f"Call {call_id} has no associated node_type")
        return None
    return node_type

class FlowLoader:
    """工作流加载器"""

    @classmethod
    async def load(cls, app_id: str, flow_id: str) -> Flow:
        """从文件系统中加载【单个】工作流"""
        flow_path = Path(config["SERVICE_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"
        with flow_path.open(encoding="utf-8") as f:
            flow_yaml = yaml.safe_load(f)

        if "name" not in flow_yaml:
            err = f"工作流名称不能为空：{flow_path!s}"
            raise ValueError(err)

        if "::" in flow_id:
            err = f"工作流名称包含非法字符：{flow_path!s}"
            raise ValueError(err)

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
                    LOGGER.error(f"Invalid edge type: {edge['type']}")

        for step in flow_yaml["steps"]:
            step["type"] = await search_step_type(step["node"])

        try:
            # 检查Flow格式，并转换为Flow对象
            flow = Flow.model_validate(flow_yaml)
        except Exception as e:
            LOGGER.error(f"Invalid flow format: {e}")
            return None

        return flow


    @classmethod
    async def save(cls, app_id: str, flow_id: str, flow: Flow) -> None:
        """保存工作流"""
        flow_path = Path(config["SERVICE_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"
        if not flow_path.parent.exists():
            flow_path.parent.mkdir(parents=True)
        if not flow_path.exists():
            flow_path.touch()
        #输出到文件
        with open(flow_path, "w", encoding="utf-8") as f:
            yaml.dump(flow.dict(), f, allow_unicode=True)



if __name__ == "__main__":
    # 测试代码
    Loader=FlowLoader()
    flow = asyncio.run(Loader.load("1","1"))
    asyncio.run(Loader.save("1","2",flow))