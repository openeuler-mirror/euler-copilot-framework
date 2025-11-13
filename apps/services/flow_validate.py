# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""flow拓扑相关函数"""

import collections
import logging

from apps.schemas.enum_var import SpecialCallType
from apps.exceptions import FlowBranchValidationError, FlowEdgeValidationError, FlowNodeValidationError
from apps.schemas.enum_var import NodeType
from apps.schemas.flow_topology import EdgeItem, FlowItem, NodeItem
from pydantic import ValidationError

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
            if node.node_id != 'start' and node.node_id != 'end' and node.node_id != SpecialCallType.EMPTY.value and node.node_id != SpecialCallType.PLUGIN.value:
                try:
                    await Pool().get_call(node.call_id)
                except Exception as e:
                    # 保存原始的serviceId和callId，以便API插件节点能够正确识别
                    original_service_id = node.service_id
                    original_call_id = node.call_id

                    # 根据是否有serviceId来判断是API插件还是普通的Empty节点
                    if original_service_id and original_service_id.strip():
                        # 有serviceId，标记为Plugin类型（API插件节点）
                        node.node_id = SpecialCallType.PLUGIN.value
                        node.call_id = SpecialCallType.PLUGIN.value
                        node.service_id = original_service_id
                        logger.info(
                            f"[FlowService] 将节点 {original_call_id} 标记为API插件节点，serviceId: {original_service_id}")
                    else:
                        # 没有serviceId，标记为Empty类型
                        node.node_id = SpecialCallType.EMPTY.value
                        node.call_id = SpecialCallType.EMPTY.value
                        logger.info(
                            f"[FlowService] 将节点 {original_call_id} 标记为Empty节点")

                    # 更新描述信息，保留原有描述
                    original_description = node.description or ""
                    node.description = f'【对应的api工具被删除！节点不可用！请联系相关人员！】\n\n{original_description}'

                    logger.error(
                        f"[FlowService] 获取步骤的call_id失败 {original_call_id}，错误: {e}")
            node_branch_map[node.step_id] = set()
            if node.call_id == NodeType.CHOICE.value:
                input_parameters = node.parameters["input_parameters"]
                if "choices" not in input_parameters:
                    err = f"[FlowService] 节点{node.name}的分支choices字段缺失"
                    logger.error(err)
                    raise FlowBranchValidationError(err)
                if not input_parameters["choices"]:
                    err = f"[FlowService] 节点{node.name}的分支choices字段为空"
                    logger.error(err)
                    raise FlowBranchValidationError(err)
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
            # FEATURE: allow one node's next_step have multiple nodes, next step node's run like stack FILO
            # if e.branch_id in branches[e.source_node]:
            #     err = f"[FlowService] 边{e.edge_id}的分支{e.branch_id}重复"
            #     logger.error(err)
            #     raise FlowEdgeValidationError(err)
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

    @classmethod
    async def validate_subflow_illegal(cls, flow: FlowItem) -> None:
        """
        验证子工作流是否违法（子工作流专用验证，不强制要求end节点）

        :param flow: 子工作流
        :raises ValidationError: 验证失败
        """
        await cls._validate_flow_nodes(flow, is_subflow=True)

    @classmethod
    async def validate_subflow_connectivity(cls, flow: FlowItem) -> bool:
        """
        验证子工作流连通性（子工作流专用，不要求连接到end节点）

        :param flow: 子工作流
        :return: 是否连通
        """
        if not flow.nodes:
            return True

        # 构建图结构
        graph = {}
        start_nodes = []

        for node in flow.nodes:
            graph[node.step_id] = []
            if node.call_id == 'start' or not any(
                edge.target_node == node.step_id for edge in flow.edges
            ):
                start_nodes.append(node.step_id)

        for edge in flow.edges:
            if edge.source_node in graph:
                graph[edge.source_node].append(edge.target_node)

        # 检查从开始节点是否能到达所有其他节点
        if not start_nodes:
            return len(flow.nodes) <= 1  # 如果没有开始节点且只有一个或零个节点，认为连通

        visited = set()

        def dfs(node_id):
            if node_id in visited:
                return
            visited.add(node_id)
            for neighbor in graph.get(node_id, []):
                dfs(neighbor)

        # 从所有开始节点开始遍历
        for start_node in start_nodes:
            dfs(start_node)

        # 检查是否所有节点都被访问到
        all_node_ids = {node.step_id for node in flow.nodes}
        return len(visited) == len(all_node_ids)

    @classmethod
    async def _validate_flow_nodes(cls, flow: FlowItem, is_subflow: bool = False) -> None:
        """
        验证工作流节点（支持子工作流模式）

        :param flow: 工作流
        :param is_subflow: 是否为子工作流
        :raises ValidationError: 验证失败
        """
        if not flow.nodes:
            raise ValidationError("工作流不能为空")

        start_count = 0
        end_count = 0

        for node in flow.nodes:
            if node.call_id == "start":
                start_count += 1
            elif node.call_id == "end":
                end_count += 1

        # 主工作流必须有start和end节点
        if not is_subflow:
            if start_count != 1:
                raise ValidationError("工作流必须有且仅有一个start节点")
            if end_count != 1:
                raise ValidationError("工作流必须有且仅有一个end节点")
        else:
            # 子工作流可以没有end节点，但如果有start节点，应该只有一个
            if start_count > 1:
                raise ValidationError("子工作流最多只能有一个start节点")
            if end_count > 1:
                raise ValidationError("子工作流最多只能有一个end节点")

        # 验证节点ID唯一性
        node_ids = [node.step_id for node in flow.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValidationError("节点ID必须唯一")

        # 验证边引用的节点存在
        for edge in flow.edges:
            source_exists = any(
                node.step_id == edge.source_node for node in flow.nodes)
            target_exists = any(
                node.step_id == edge.target_node for node in flow.nodes)

            if not source_exists:
                raise ValidationError(f"边引用的源节点不存在: {edge.source_node}")
            if not target_exists:
                raise ValidationError(f"边引用的目标节点不存在: {edge.target_node}")
