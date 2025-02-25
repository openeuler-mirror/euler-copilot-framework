"""Node管理器"""
from typing import Any, Optional

import ray

from apps.constants import LOGGER
from apps.entities.node import APINode
from apps.entities.pool import CallPool, Node, NodePool
from apps.models.mongo import MongoDB

NODE_TYPE_MAP = {
    "API": APINode,
}

class NodeManager:
    """Node管理器"""

    @staticmethod
    async def get_node_call_id(node_id: str) -> str:
        """获取Node的call_id"""
        node_collection = MongoDB().get_collection("node")
        node = await node_collection.find_one({"id": node_id}, {"call_id": 1})
        if not node:
            err = f"[NodeManager] Node {node_id} not found."
            raise ValueError(err)
        return node["call_id"]


    @staticmethod
    async def get_node_name(node_id: str) -> str:
        """获取node的名称"""
        node_collection = MongoDB.get_collection("node")
        # 查询 Node 集合获取对应的 name
        node_doc = await node_collection.find_one({"_id": node_id}, {"name": 1})
        if not node_doc:
            LOGGER.error(f"Node {node_id} not found")
            return ""
        return node_doc["name"]


    @staticmethod
    def merge_params_schema(params_schema: dict[str, Any], known_params: dict[str, Any]) -> dict[str, Any]:
        """合并参数Schema"""
        pass


    @staticmethod
    async def get_node_data(node_id: str) -> Optional[Node]:
        """获取Node数据"""
        # 查找Node信息
        node_collection = MongoDB().get_collection("node")
        try:
            node = await node_collection.find_one({"id": node_id})
            node_data = NodePool.model_validate(node)
        except Exception as e:
            err = f"[NodeManager] Get node data error: {e}"
            LOGGER.error(err)
            raise ValueError(err) from e

        call_id = node_data.call_id
        # 查找Node对应的Call信息
        call_collection = MongoDB().get_collection("call")
        try:
            call = await call_collection.find_one({"id": call_id})
            call_data = CallPool.model_validate(call)
        except Exception as e:
            err = f"[NodeManager] Get call data error: {e}"
            LOGGER.error(err)
            raise ValueError(err) from e

        # 查找Call信息
        pool = ray.get_actor("pool")
        call_class = await pool.get_call.remote(call_data.path)
        if not call_class:
            err = f"[NodeManager] Call {call_data.path} not found"
            LOGGER.error(err)
            raise ValueError(err)

        # 找到Call的参数
        result_node = Node(
            _id=node_data.id,
            name=node_data.name,
            description=node_data.description,
            created_at=node_data.created_at,
            service_id=node_data.service_id,
            call_id=node_data.call_id,
            output_schema=call_class.output_schema,
            params_schema=NodeManager.merge_params_schema(call_class.params_schema, node_data.known_params or {}),
        )

        return call_class

