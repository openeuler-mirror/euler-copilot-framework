"""flow拓扑相关函数

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
import queue

from apps.entities.enum_var import NodeType
from apps.entities.flow_topology import EdgeItem, FlowItem, NodeItem

logger = logging.getLogger("ray")


class FlowService:
    """flow拓扑相关函数"""

    @staticmethod
    async def remove_excess_structure_from_flow(flow_item: FlowItem) -> FlowItem:
        """移除流程图中的多余结构"""
        node_to_branches = {}
        branch_illegal_chars="."

        for node in flow_item.nodes:
            node_to_branches[node.step_id] = set()
            if node.call_id == NodeType.CHOICE.value:
                node.parameters = node.parameters["input_parameters"]
                if "choices" not in node.parameters:
                    node.parameters["choices"] = []
                for branch in node.parameters["choices"]:
                    if branch["branchId"] in node_to_branches[node.step_id]:
                        err = f"[FlowService] 节点{node.name}的分支{branch['branchId']}重复"
                        logger.error(err)
                        raise Exception(err)
                    for illegal_char in branch_illegal_chars:
                        if illegal_char in branch["branchId"]:
                            err = f"[FlowService] 节点{node.name}的分支{branch['branchId']}名称中含有非法字符"
                            logger.error(err)
                            raise Exception(err)
                    node_to_branches[node.step_id].add(branch["branchId"])
            else:
                node_to_branches[node.step_id].add("")
        new_edges_items = []
        for edge in flow_item.edges:
            if edge.source_node not in node_to_branches:
                continue
            if edge.target_node not in node_to_branches:
                continue
            if edge.branch_id not in node_to_branches[edge.source_node]:
                continue
            new_edges_items.append(edge)
        flow_item.edges = new_edges_items
        return flow_item

    @staticmethod
    async def _validate_node_ids(nodes: list[NodeItem]) -> tuple[str, str]:
        """验证节点ID的唯一性并获取起始和终止节点ID，当节点ID重复或起始/终止节点数量不为1时抛出异常"""
        ids = set()
        start_cnt = 0
        end_cnt = 0
        start_id = None
        end_id = None

        for node in nodes:
            if node.step_id in ids:
                err = f"[FlowService] 节点{node.name}的id重复"
                logger.error(err)
                raise Exception(err)
            ids.add(node.step_id)
            if node.call_id == NodeType.START.value:
                start_cnt += 1
                start_id = node.step_id
            if node.call_id == NodeType.END.value:
                end_cnt += 1
                end_id = node.step_id

        if start_cnt != 1 or end_cnt != 1:
            err = "[FlowService] 起始节点和终止节点数量不为1"
            logger.error(err)
            raise Exception(err)

        if start_id is None or end_id is None:
            err = "[FlowService] 起始节点或终止节点ID为空"
            logger.error(err)
            raise Exception(err)

        return start_id, end_id

    @staticmethod
    async def _validate_edges(edges: list[EdgeItem]) -> tuple[dict[str, int], dict[str, int]]:
        """验证边的合法性并计算节点的入度和出度；当边的ID重复、起始终止节点相同或分支重复时抛出异常"""
        ids = set()
        branches = {}
        in_deg = {}
        out_deg = {}

        for e in edges:
            if e.edge_id in ids:
                err = f"[FlowService] 边{e.edge_id}的id重复"
                logger.error(err)
                raise Exception(err)
            ids.add(e.edge_id)

            if e.source_node == e.target_node:
                err = f"[FlowService] 边{e.edge_id}的起始节点和终止节点相同"
                logger.error(err)
                raise Exception(err)

            if e.source_node not in branches:
                branches[e.source_node] = set()
            if e.branch_id in branches[e.source_node]:
                err = f"[FlowService] 边{e.edge_id}的分支{e.branch_id}重复"
                logger.error(err)
                raise Exception(err)
            branches[e.source_node].add(e.branch_id)

            in_deg[e.target_node] = in_deg.get(e.target_node, 0) + 1
            out_deg[e.source_node] = out_deg.get(e.source_node, 0) + 1

        return in_deg, out_deg

    @staticmethod
    async def _validate_node_degrees(start_id: str, end_id: str,
                                   in_deg: dict[str, int], out_deg: dict[str, int]) -> None:
        """验证起始和终止节点的入度和出度；当起始节点入度不为0或终止节点出度不为0时抛出异常"""
        if start_id in in_deg and in_deg[start_id] != 0:
            err = f"[FlowService] 起始节点{start_id}的入度不为0"
            logger.error(err)
            raise Exception(err)
        if end_id in out_deg and out_deg[end_id] != 0:
            err = f"[FlowService] 终止节点{end_id}的出度不为0"
            logger.error(err)
            raise Exception(err)

    @staticmethod
    async def validate_flow_illegal(flow_item: FlowItem) -> None:
        """验证流程图是否合法；当流程图不合法时抛出异常"""
        # 验证节点ID并获取起始和终止节点
        start_id, end_id = await FlowService._validate_node_ids(flow_item.nodes)

        # 验证边的合法性并获取节点的入度和出度
        in_deg, out_deg = await FlowService._validate_edges(flow_item.edges)

        # 验证起始和终止节点的入度和出度
        await FlowService._validate_node_degrees(start_id, end_id, in_deg, out_deg)

    @staticmethod
    async def validate_flow_connectivity(flow_item: FlowItem) -> None:
        id_of_start_node = None
        step_id_set=set()
        node_edge_dict={}
        for node in flow_item.nodes:
            if node.call_id == NodeType.START.value:
                id_of_start_node = node.step_id
        for edge in flow_item.edges:
            if edge.source_node not in node_edge_dict:
                node_edge_dict[edge.source_node] = []
            node_edge_dict[edge.target_node].append(edge.target_node)
        node_q=queue.Queue()
        node_q.put(id_of_start_node)
        node_reached_cnt=0
        step_id_set.add(id_of_start_node)
        while len(node_q)>0:
            step_id=node_q.get()
            node_reached_cnt+=1
            if step_id in node_edge_dict:
                for target_node in node_edge_dict[step_id]:
                    if target_node not in step_id_set:
                        step_id_set.add(target_node)
                        node_q.put(target_node)
        if node_reached_cnt!=len(flow_item.nodes):
            err = "[FlowService] 流程图存在孤立子图"
            logger.error(err)
            raise Exception(err)

def generate_from_schema(schema: dict) -> dict:
    """根据 JSON Schema 生成示例 JSON 数据。

    :param schema: JSON Schema 字典
    :return: 生成的示例 JSON 数据
    """
    def _generate_example(schema_node: dict):
        # 处理类型为 object 的节点
        if schema_node.get("type") == "object":
            example = {}
            properties = schema_node.get("properties", {})
            for prop_name, prop_schema in properties.items():
                example[prop_name] = _generate_example(prop_schema)
            return example

        # 处理类型为 array 的节点
        if schema_node.get("type") == "array":
            items_schema = schema_node.get("items", {})
            return [_generate_example(items_schema)]

        # 处理类型为 string 的节点
        if schema_node.get("type") == "string":
            return schema_node.get("default", "example_string")

        # 处理类型为 number 或 integer 的节点
        if schema_node.get("type") in ["number", "integer"]:
            return schema_node.get("default", 0)

        # 处理类型为 boolean 的节点
        if schema_node.get("type") == "boolean":
            return schema_node.get("default", False)

        # 处理其他类型或未定义类型
        return None


    # 生成示例数据
    return _generate_example(schema)