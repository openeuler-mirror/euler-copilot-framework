# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Node管理器"""

import logging
from typing import TYPE_CHECKING, Any

from apps.common.mongo import MongoDB
from apps.schemas.node import APINode
from apps.schemas.pool import NodePool

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)
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
    async def get_node(node_id: str) -> NodePool:
        """获取Node的类型"""
        node_collection = MongoDB().get_collection("node")
        node = await node_collection.find_one({"_id": node_id})
        if not node:
            err = f"[NodeManager] Node {node_id} not found."
            raise ValueError(err)
        return NodePool.model_validate(node)

    @staticmethod
    async def get_node_name(node_id: str) -> str:
        """获取node的名称"""
        node_collection = MongoDB().get_collection("node")
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
        from apps.scheduler.pool.pool import Pool

        # 查找Node信息
        logger.info("[NodeManager] 获取节点 %s", node_id)
        node_collection = MongoDB().get_collection("node")
        node = await node_collection.find_one({"_id": node_id})
        if not node:
            err = f"[NodeManager] Node {node_id} not found."
            logger.error(err)
            raise ValueError(err)

        node_data = NodePool.model_validate(node)
        call_id = node_data.call_id

        # 查找Call信息
        logger.info("[NodeManager] 获取Call %s", call_id)
        call_class: type[BaseModel] = await Pool().get_call(call_id)
        if not call_class:
            err = f"[NodeManager] Call {call_id} 不存在"
            logger.error(err)
            raise ValueError(err)
        # 生成输出参数Schema
        output_schema = call_class.output_model.model_json_schema(  # type: ignore[attr-defined]
            override=node_data.override_output if node_data.override_output else {},
        )
        
        # 特殊处理：对于循环节点，直接返回扁平化的输出参数结构
        if call_id == "Loop":
            # 直接使用正确的扁平化格式，避免依赖JSON Schema转换
            output_schema = {
                "iteration_count": {
                    "type": "integer",
                    "description": "实际执行的循环次数"
                },
                "stop_reason": {
                    "type": "string", 
                    "description": "停止原因"
                },
                "variables": {
                    "type": "object",
                    "description": "循环后的变量状态"
                }
            }
        elif call_id == "FileExtract":
            # 文件提取器节点的输出参数
            output_schema = {
                "text": {
                    "type": "string",
                    "description": "提取的文本内容"
                }
            }
        
        # 返回参数Schema
        return (
            NodeManager.merge_params_schema(call_class.model_json_schema(), node_data.known_params or {}),
            output_schema,
        )
