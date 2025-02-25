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
        node = await node_collection.find_one({"_id": node_id}, {"call_id": 1})
        if not node:
            err = f"[NodeManager] Node call_id {node_id} not found."
            raise ValueError(err)
        return node["call_id"]

    @staticmethod
    async def get_node_name(node_id: str) -> str:
        """获取Node的名称"""
        node_collection = MongoDB().get_collection("node")
        node = await node_collection.find_one({"_id": node_id}, {"name": 1})
        if not node:
            err = f"[NodeManager] Node name_id {node_id} not found."
            raise ValueError(err)
        return node["name"]
