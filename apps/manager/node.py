"""Node管理器"""
import logging
from typing import Any

import ray
from pydantic import BaseModel

from apps.entities.node import APINode
from apps.entities.pool import CallPool, NodePool
from apps.models.mongo import MongoDB

logger = logging.getLogger("ray")
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
        """获取node的名称"""
        node_collection = MongoDB.get_collection("node")
        # 查询 Node 集合获取对应的 name
        node_doc = await node_collection.find_one({"_id": node_id}, {"name": 1})
        if not node_doc:
            logger.error("[NodeManager] Node %s not found", node_id)
            return ""
        return node_doc["name"]


    @staticmethod
    def merge_params_schema(params_schema: dict[str, Any], known_params: dict[str, Any]) -> dict[str, Any]:
        """递归合并参数Schema，将known_params中的值填充到params_schema的对应位置"""
        if not isinstance(params_schema, dict):
            return params_schema

        if params_schema.get("type") == "object":
            properties = params_schema.get("properties", {})
            for key, value in properties.items():
                if key in known_params:
                    # 如果在known_params中找到匹配的键，更新default值
                    properties[key]["default"] = known_params[key]
                # 递归处理嵌套的schema
                properties[key] = NodeManager.merge_params_schema(value, known_params)

        elif params_schema.get("type") == "array":
            items = params_schema.get("items", {})
            # 递归处理数组项
            params_schema["items"] = NodeManager.merge_params_schema(items, known_params)

        return params_schema


    @staticmethod
    async def get_node_params(node_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """获取Node数据"""
        # 查找Node信息
        logger.info("[NodeManager] 获取节点 %s", node_id)
        node_collection = MongoDB().get_collection("node")
        node = await node_collection.find_one({"_id": node_id})
        if not node:
            err = f"[NodeManager] Node {node_id} not found."
            logger.error(err)
            raise ValueError(err)

        try:
            node_data = NodePool.model_validate(node)
        except Exception as e:
            err = "[NodeManager] 获取节点数据失败"
            logger.exception(err)
            raise ValueError(err) from e

        call_id = node_data.call_id
        # 查找Node对应的Call信息
        call_collection = MongoDB().get_collection("call")
        call = await call_collection.find_one({"_id": call_id})
        if not call:
            err = f"[NodeManager] Call {call_id} not found."
            logger.error(err)
            raise ValueError(err)

        try:
            call_data = CallPool.model_validate(call)
        except Exception as e:
            err = "[NodeManager] 获取Call数据失败"
            logger.exception(err)
            raise ValueError(err) from e

        # 查找Call信息
        logger.info("[NodeManager] 获取Call %s", call_data.path)
        pool = ray.get_actor("pool")
        call_class: type[BaseModel] = await pool.get_call.remote(call_data.path)
        if not call_class:
            err = f"[NodeManager] Call {call_data.path} not found"
            logger.error(err)
            raise ValueError(err)

        # 返回参数Schema
        return (
            NodeManager.merge_params_schema(call_class.model_json_schema(), node_data.known_params or {}),
            call_class.ret_type.model_json_schema(), # type: ignore[attr-defined]
        )
