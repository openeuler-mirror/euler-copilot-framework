"""flow拓扑相关函数

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import queue
from apps.constants import LOGGER
from apps.entities.enum_var import NodeType
from apps.entities.flow_topology import FlowItem


class FlowService:
    @staticmethod
    async def remove_excess_structure_from_flow(flow_item: FlowItem) -> FlowItem:
        node_to_branches = dict()
        branch_illegal_chars='.'
        for node in flow_item.nodes:
            node_to_branches[node.step_id] = set()
            if node.call_id == NodeType.CHOICE.value:
                node.parameters = node.parameters["input_parameters"]
                if 'choices' not in node.parameters.keys():
                    node.parameters['choices'] = []
                for branch in node.parameters['choices']:
                    if branch['branchId'] in node_to_branches[node.step_id]:
                        LOGGER.error(msg="分支id重复")
                        raise Exception(f"节点{node.name}的分支{branch['branchId']}重复")
                    for illegal_char in branch_illegal_chars:
                        if illegal_char in branch['branchId']:
                            LOGGER.error(msg="分支名称中含有非法字符")
                            raise Exception(f"节点{node.name}的分支{branch['branchId']}名称中含有非法字符")
                    node_to_branches[node.step_id].add(branch['branchId'])
            else:
                node_to_branches[node.step_id].add('')
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
    async def validate_flow_illegal(flow_item: FlowItem) -> None:
        step_id_set = set()
        edge_id_set = set()
        edge_to_branch = dict()
        num_of_start_node = 0
        num_of_end_node = 0
        id_of_start_node = None
        id_of_end_node = None
        node_in_degrees = {}
        node_out_degrees = {}
        for node in flow_item.nodes:
            if node.step_id in step_id_set:
                LOGGER.error(msg="节点id重复")
                raise Exception(f"节点{node.name}的id重复")
            step_id_set.add(node.step_id)
            if node.call_id == NodeType.START.value:
                num_of_start_node += 1
                id_of_start_node = node.step_id
            if node.call_id == NodeType.END.value:
                num_of_end_node += 1
                id_of_end_node = node.step_id
        if num_of_start_node != 1 or num_of_end_node != 1:
            LOGGER.error(msg="起始节点和终止节点数量不为1")
            raise Exception("起始节点和终止节点数量不为1")
        for edge in flow_item.edges:
            if edge.edge_id in edge_id_set:
                LOGGER.error(msg="边id重复")
                raise Exception(f"边{edge.edge_id}的id重复")
            edge_id_set.add(edge.edge_id)
            if edge.source_node == edge.target_node:
                LOGGER.error(msg="边起始节点和终止节点相同")
                raise Exception(f"边{edge.edge_id}的起始节点和终止节点相同")
            if edge.source_node not in edge_to_branch:
                edge_to_branch[edge.source_node] = set()
            if edge.branch_id in edge_to_branch[edge.source_node]:
                LOGGER.error(msg=f"边{edge.edge_id}的分支{edge.branch_id}重复")
                raise Exception(f"边{edge.edge_id}的分支{edge.branch_id}重复")
            edge_to_branch[edge.source_node].add(edge.branch_id)
            node_in_degrees[edge.target_node] = node_in_degrees.get(
                edge.target_node, 0) + 1
            node_out_degrees[edge.source_node] = node_out_degrees.get(
                edge.source_node, 0) + 1
        if id_of_start_node in node_in_degrees.keys() and node_in_degrees[id_of_start_node] != 0:
            LOGGER.error(msg=f"起始节点{id_of_start_node}的入度不为0")
            raise Exception(f"起始节点{id_of_start_node}的入度不为0")
        if id_of_end_node in node_out_degrees.keys() and node_out_degrees[id_of_end_node] != 0:
            LOGGER.error(msg=f"终止节点{id_of_end_node}的出度不为0")
            raise Exception(f"终止节点{id_of_end_node}的出度不为0")

    @staticmethod
    async def validate_flow_connectivity(flow_item: FlowItem) -> None:
        id_of_start_node = None
        step_id_set=set()
        node_edge_dict={}
        for node in flow_item.nodes:
            if node.call_id == NodeType.START.value:
                id_of_start_node = node.step_id
        for edge in flow_item.edges:
            if edge.source_node not in node_edge_dict.keys():
                node_edge_dict[edge.source_node] = []
            node_edge_dict[edge.target_node].append(edge.target_node)
        node_q=queue.Queue()
        node_q.put(id_of_start_node)
        node_reached_cnt=0
        step_id_set.add(id_of_start_node)
        while len(node_q)>0:
            step_id=node_q.get()
            node_reached_cnt+=1
            if step_id in node_edge_dict.keys():
                for target_node in node_edge_dict[step_id]:
                    if target_node not in step_id_set:
                        step_id_set.add(target_node)
                        node_q.put(target_node)
        if node_reached_cnt!=len(flow_item.nodes):
            LOGGER.error(msg="流程图存在孤立子图")
            raise Exception("流程图存在孤立子图")

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
        elif schema_node.get("type") == "array":
            items_schema = schema_node.get("items", {})
            return [_generate_example(items_schema)]

        # 处理类型为 string 的节点
        elif schema_node.get("type") == "string":
            return schema_node.get("default", "example_string")

        # 处理类型为 number 或 integer 的节点
        elif schema_node.get("type") in ["number", "integer"]:
            return schema_node.get("default", 0)

        # 处理类型为 boolean 的节点
        elif schema_node.get("type") == "boolean":
            return schema_node.get("default", False)

        # 处理其他类型或未定义类型
        else:
            return None


    # 生成示例数据
    return _generate_example(schema)