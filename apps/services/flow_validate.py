# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""flow拓扑相关函数"""

import collections
import logging

from apps.schemas.enum_var import SpecialCallType
from apps.exceptions import FlowBranchValidationError, FlowEdgeValidationError, FlowNodeValidationError
from apps.schemas.enum_var import NodeType
from apps.schemas.flow_topology import EdgeItem, FlowItem, NodeItem

logger = logging.getLogger(__name__)


class FlowService:
    """flow拓扑相关函数"""

    @staticmethod
    def _validate_branch_id(
        node_name: str, branch_id: str, node_branches: set, branch_illegal_chars: str = ".",
    ) -> None:
        """验证分支ID的合法性；当分支ID重复或包含非法字符时抛出异常"""
        if branch_id in node_branches:
            err = f"[FlowService] 节点{node_name}的分支{branch_id}重复"
            logger.error(err)
            raise FlowBranchValidationError(err)

        for illegal_char in branch_illegal_chars:
            if illegal_char in branch_id:
                err = f"[FlowService] 节点{node_name}的分支{branch_id}名称中含有非法字符"
                logger.error(err)
                raise FlowBranchValidationError(err)

    @staticmethod
    async def remove_excess_structure_from_flow(flow_item: FlowItem) -> FlowItem:
        """移除流程图中的多余结构"""
        node_branch_map = {}
        branch_illegal_chars = "."
        for node in flow_item.nodes:
            from apps.scheduler.pool.pool import Pool
            from pydantic import BaseModel
            if node.node_id != 'start' and node.node_id != 'end' and node.node_id != SpecialCallType.EMPTY.value:
                try:
                    call_class: type[BaseModel] = await Pool().get_call(node.call_id)
                    if not call_class:
                        node.node_id = SpecialCallType.EMPTY.value
                        node.description = '【对应的api工具被删除！节点不可用！请联系相关人员！】\n\n'+node.description
                except Exception as e:
                    node.node_id = SpecialCallType.EMPTY.value
                    node.description = '【对应的api工具被删除！节点不可用！请联系相关人员！】\n\n'+node.description
                    logger.error(f"[FlowService] 获取步骤的call_id失败{node.call_id}由于：{e}")
            node_branch_map[node.step_id] = set()
            if node.call_id == NodeType.CHOICE.value:
                input_parameters = node.parameters["input_parameters"]
                if "choices" not in input_parameters:
                    logger.error(f"[FlowService] 节点{node.name}的分支字段缺失")
                    raise FlowBranchValidationError(f"[FlowService] 节点{node.name}的分支字段缺失")
                if not input_parameters["choices"]:
                    logger.error(f"[FlowService] 节点{node.name}的分支字段为空")
                    raise FlowBranchValidationError(f"[FlowService] 节点{node.name}的分支字段为空")
                for choice in input_parameters["choices"]:
                    if "branch_id" not in choice:
                        err = f"[FlowService] 节点{node.name}的分支choice缺少branch_id字段"
                        logger.error(err)
                        raise FlowBranchValidationError(err)
                    if choice["branch_id"] in node_branch_map[node.step_id]:
                        err = f"[FlowService] 节点{node.name}的分支{choice['branch_id']}重复"
                        logger.error(err)
                        raise Exception(err)
                    for illegal_char in branch_illegal_chars:
                        if illegal_char in choice["branch_id"]:
                            err = f"[FlowService] 节点{node.name}的分支{choice['branch_id']}名称中含有非法字符"
                            logger.error(err)
                            raise Exception(err)
                    node_branch_map[node.step_id].add(choice["branch_id"])
            else:
                node_branch_map[node.step_id].add("")
        valid_edges = []
        for edge in flow_item.edges:
            if edge.source_node not in node_branch_map:
                continue
            if edge.target_node not in node_branch_map:
                continue
            if edge.branch_id not in node_branch_map[edge.source_node]:
                continue
            valid_edges.append(edge)
        flow_item.edges = valid_edges
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
                raise FlowNodeValidationError(err)
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
            raise FlowNodeValidationError(err)

        if start_id is None or end_id is None:
            err = "[FlowService] 起始节点或终止节点ID为空"
            logger.error(err)
            raise FlowNodeValidationError(err)

        return start_id, end_id

    @staticmethod
    async def validate_flow_illegal(flow_item: FlowItem) -> tuple[str, str]:
        """验证流程图是否合法；当流程图不合法时抛出异常"""
        # 验证节点ID并获取起始和终止节点
        start_id, end_id = await FlowService._validate_node_ids(flow_item.nodes)

        # 验证边的合法性并获取节点的入度和出度
        in_deg, out_deg = await FlowService._validate_edges(flow_item.edges)

        # 验证起始和终止节点的入度和出度
        await FlowService._validate_node_degrees(start_id, end_id, in_deg, out_deg)

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
                raise FlowEdgeValidationError(err)
            ids.add(e.edge_id)

            if e.source_node == e.target_node:
                err = f"[FlowService] 边{e.edge_id}的起始节点和终止节点相同"
                logger.error(err)
                raise FlowEdgeValidationError(err)

            if e.source_node not in branches:
                branches[e.source_node] = set()
            if e.branch_id in branches[e.source_node]:
                err = f"[FlowService] 边{e.edge_id}的分支{e.branch_id}重复"
                logger.error(err)
                raise FlowEdgeValidationError(err)
            branches[e.source_node].add(e.branch_id)

            in_deg[e.target_node] = in_deg.get(e.target_node, 0) + 1
            out_deg[e.source_node] = out_deg.get(e.source_node, 0) + 1

        return in_deg, out_deg

    @staticmethod
    async def _validate_node_degrees(
        start_id: str, end_id: str, in_deg: dict[str, int], out_deg: dict[str, int],
    ) -> None:
        """验证起始和终止节点的入度和出度；当起始节点入度不为0或终止节点出度不为0时抛出异常"""
        if start_id in in_deg and in_deg[start_id] != 0:
            err = f"[FlowService] 起始节点{start_id}的入度不为0"
            logger.error(err)
            raise FlowNodeValidationError(err)
        if end_id in out_deg and out_deg[end_id] != 0:
            err = f"[FlowService] 终止节点{end_id}的出度不为0"
            logger.error(err)
            raise FlowNodeValidationError(err)

    @staticmethod
    def _find_start_node_id(nodes: list[NodeItem]) -> str:
        """查找起始节点ID"""
        for node in nodes:
            if node.call_id == NodeType.START.value:
                return node.step_id
        return ""

    @staticmethod
    def _build_adjacency_list(edges: list[EdgeItem]) -> dict[str, list[str]]:
        """构建邻接表"""
        adj_list = {}
        for edge in edges:
            if edge.source_node not in adj_list:
                adj_list[edge.source_node] = []
            adj_list[edge.source_node].append(edge.target_node)
        return adj_list

    @staticmethod
    def _bfs_traverse(start_id: str, adj_list: dict[str, list[str]]) -> set[str]:
        """使用BFS遍历图并返回可达节点集合"""
        visited = set()
        if not start_id:
            return visited

        queue = collections.deque([start_id])
        visited.add(start_id)

        while queue:
            current = queue.popleft()
            if current in adj_list:
                for neighbor in adj_list[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
        return visited

    @staticmethod
    async def validate_flow_connectivity(flow_item: FlowItem) -> bool:
        """
        验证流程图的连通性

        检查:
        1. 是否所有节点都能从起始节点到达
        2. 是否能从起始节点到达终止节点
        3. 是否存在非终止节点没有出边
        """
        # 找到起始和终止节点
        start_id = None
        end_id = None
        for node in flow_item.nodes:
            if node.call_id == NodeType.START.value:
                start_id = node.step_id
            if node.call_id == NodeType.END.value:
                end_id = node.step_id

        # 构建邻接表
        adj = {}
        for edge in flow_item.edges:
            if edge.source_node not in adj:
                adj[edge.source_node] = []
            adj[edge.source_node].append(edge.target_node)

        # BFS遍历检查连通性
        vis = {start_id}
        q = [start_id]  # 使用list替代queue.Queue

        while q:  # 使用while q替代while not q.empty()
            cur = q.pop(0)  # 使用pop(0)替代q.get()
            # 检查非终止节点是否有出边
            if cur != end_id and cur not in adj:
                return False

            # 遍历所有出边
            if cur in adj:
                for nxt in adj[cur]:
                    if nxt not in vis:
                        vis.add(nxt)
                        q.append(nxt)  # 使用append替代q.put()

        # 检查是否能到达终止节点
        return end_id in vis
