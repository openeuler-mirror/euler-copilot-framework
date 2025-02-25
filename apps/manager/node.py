"""Node管理器"""
from apps.models.mongo import MongoDB


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
        """获取Node的名称"""
        node_collection = MongoDB().get_collection("node")
        node = await node_collection.find_one({"id": node_id}, {"name": 1})
        if not node:
            err = f"[NodeManager] Node {node_id} not found."
            raise ValueError(err)
        return node["name"]