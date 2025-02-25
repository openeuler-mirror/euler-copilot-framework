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
            node_to_branches[node.node_id] = set()
            if node.type == NodeType.CHOICE.value:
                node.parameters = node.parameters["input_parameters"]
                if 'choices' not in node.parameters.keys():
                    node.parameters['choices'] = []
                for branch in node.parameters['choices']:
                    if branch['branchId'] in node_to_branches[node.node_id]:
                        LOGGER.error(msg="分支id重复")
                        raise Exception(f"节点{node.name}的分支{branch['branchId']}重复")
                    for illegal_char in branch_illegal_chars:
                        if illegal_char in branch['branchId']:
                            LOGGER.error(msg="分支名称中含有非法字符")
                            raise Exception(f"节点{node.name}的分支{branch['branchId']}名称中含有非法字符")
                    node_to_branches[node.node_id].add(branch['branchId'])
            else:
                node_to_branches[node.node_id].add('')
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
        node_id_set = set()
        edge_id_set = set()
        edge_to_branch = dict()
        num_of_start_node = 0
        num_of_end_node = 0
        id_of_start_node = None
        id_of_end_node = None
        node_in_degrees = {}
        node_out_degrees = {}
        for node in flow_item.nodes:
            if node.node_id in node_id_set:
                LOGGER.error(msg="节点id重复")
                raise Exception(f"节点{node.name}的id重复")
            node_id_set.add(node.node_id)
            if node.type == NodeType.START.value:
                num_of_start_node += 1
                id_of_start_node = node.node_id
            if node.type == NodeType.END.value:
                num_of_end_node += 1
                id_of_end_node = node.node_id
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
        node_id_set=set()
        node_edge_dict={}
        for node in flow_item.nodes:
            if node.type == NodeType.START.value:
                id_of_start_node = node.node_id
        for edge in flow_item.edges:
            if edge.source_node not in node_edge_dict.keys():
                node_edge_dict[edge.source_node] = []
            node_edge_dict[edge.target_node].append(edge.target_node)
        node_q=queue.Queue()
        node_q.put(id_of_start_node)
        node_reached_cnt=0
        node_id_set.add(id_of_start_node)
        while len(node_q)>0:
            node_id=node_q.get()
            node_reached_cnt+=1
            if node_id in node_edge_dict.keys():
                for target_node in node_edge_dict[node_id]:
                    if target_node not in node_id_set:
                        node_id_set.add(target_node)
                        node_q.put(target_node)
        if node_reached_cnt!=len(flow_item.nodes):
            LOGGER.error(msg="流程图存在孤立子图")
            raise Exception("流程图存在孤立子图")
        

