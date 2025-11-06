# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""flow Manager"""

import logging
import uuid

from sqlalchemy import and_, delete, select

from apps.common.postgres import postgres
from apps.models import (
    App,
    AppHashes,
    NodeInfo,
    Service,
    UserFavorite,
    UserFavoriteType,
)
from apps.models import Flow as FlowInfo
from apps.scheduler.pool.pool import pool
from apps.scheduler.slot.slot import Slot
from apps.schemas.enum_var import EdgeType
from apps.schemas.flow import FlowAppMetadata, Edge, Flow, PositionItem, Step
from apps.schemas.flow_topology import (
    EdgeItem,
    FlowItem,
    NodeItem,
    NodeMetaDataBase,
    NodeMetaDataItem,
    NodeServiceItem,
)

from .node import NodeManager

FLOW_SPLIT_LEN = 2
logger = logging.getLogger(__name__)


class FlowManager:
    """Flow相关操作"""

    @staticmethod
    async def get_flows_by_app_id(app_id: uuid.UUID) -> list[FlowInfo]:
        """
        通过appId获取应用的所有flow

        :param app_id: 应用的id
        :return: flow列表
        """
        async with postgres.session() as session:
            return list((await session.scalars(
                select(FlowInfo).where(FlowInfo.appId == app_id),
            )).all())

    @staticmethod
    async def get_node_id_by_service_id(service_id: uuid.UUID) -> list[NodeMetaDataBase] | None:
        """
        根据serviceId获取service内节点的基础信息，用于左侧节点列表展示

        :param service_id: 服务id
        :return: 节点基础信息的列表，按创建时间排序
        """
        async with postgres.session() as session:
            node_data = list((await session.scalars(
                select(NodeInfo.id, NodeInfo.callId, NodeInfo.name, NodeInfo.updatedAt).where(
                    NodeInfo.serviceId == service_id,
                ).order_by(NodeInfo.updatedAt.desc()),
            )).all())

            # 进行格式转换
            result = []
            for item in node_data:
                result += [NodeMetaDataBase(
                    nodeId=item.id,
                    callId=item.callId,
                    name=item.name,
                    updatedAt=round(item.updatedAt.timestamp(), 3),
                )]
            return result


    @staticmethod
    async def get_service_by_user(user_id: str) -> list[NodeServiceItem] | None:
        """
        通过user_id获取用户自己上传的或收藏的Service，用于插件中心展示

        :param user_id: str: 用户的唯一标识符
        :return: service的列表
        """
        async with postgres.session() as session:
            service_ids = []
            # 用户所有收藏的服务
            user_favs = list((await session.scalars(
                select(UserFavorite.itemId).where(
                    and_(
                        UserFavorite.userId == user_id,
                        UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                    ),
                ),
            )).all())
            service_ids = service_ids + user_favs
            # 用户所上传的Service
            user_services = list((await session.scalars(
                select(Service.id).where(
                    Service.authorId == user_id,
                ),
            )).all())
            service_ids = service_ids + user_services
            service_ids = list(set(service_ids))

            # 获取Service
            service_data = list((await session.scalars(
                select(Service).where(
                    Service.id.in_(service_ids),
                ).order_by(Service.updatedAt.desc()),
            )).all())

            # 组装返回值
            service_items = [NodeServiceItem(
                serviceId=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                name="系统",
                data=[],
                createdAt=None,
            )]
            service_items += [
                NodeServiceItem(
                    serviceId=item.id,
                    name=item.name,
                    data=[],
                    createdAt=str(item.updatedAt.timestamp()),
                )
                for item in service_data
            ]

            for service_item in service_items:
                node_meta_datas = await FlowManager.get_node_id_by_service_id(service_item.service_id)
                if node_meta_datas is None:
                    node_meta_datas = []
                service_item.data = node_meta_datas

            return service_items


    @staticmethod
    async def get_node_by_node_id(node_id: str) -> NodeMetaDataItem | None:
        """
        通过node_id获取对应的节点元数据信息

        :param node_id: node的id
        :return: node_id对应的节点元数据信息
        """
        async with postgres.session() as session:
            node_data = (await session.scalars(
                select(NodeInfo).where(NodeInfo.id == node_id),
            )).one_or_none()
            # 判断如果没有Node
            if node_data is None:
                err = f"[FlowManager] 节点元数据 {node_id} 不存在"
                logger.error(err)
                raise ValueError(err)

            # 处理Schema
            params_schema, output_schema = await NodeManager.get_node_params(node_data.id)
            parameters = {
                "input_parameters": Slot(params_schema).create_empty_slot(),
                "output_parameters": Slot(output_schema).extract_type_desc_from_schema(),
            }

            return NodeMetaDataItem(
                nodeId=node_data.id,
                callId=node_data.callId,
                name=node_data.name,
                description=node_data.description,
                parameters=parameters,
                updatedAt=round(node_data.updatedAt.timestamp(), 3),
            )


    @staticmethod
    async def get_flow_by_app_and_flow_id(app_id: uuid.UUID, flow_id: str) -> FlowItem | None:
        """
        通过appId flowId获取flow config的路径和focus，并通过flow config的路径获取flow config，并将其转换为flow item。

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的item和用户在这个流上的视觉焦点
        """
        async with postgres.session() as session:
            flow_data = (await session.scalars(
                select(FlowInfo).where(and_(FlowInfo.appId == app_id, FlowInfo.id == flow_id)),
            )).one_or_none()
            if flow_data is None:
                err = f"[FlowManager] 流 {flow_id} 不存在"
                logger.error(err)
                raise ValueError(err)

            flow_config = await pool.flow_loader.load(app_id, flow_id)
            flow_item = FlowItem(
                flowId=flow_id,
                name=flow_config.name,
                description=flow_config.description,
                enable=True,
                nodes=[],
                edges=[],
                checkStatus=flow_config.checkStatus,
                basicConfig=flow_config.basicConfig,
            )

            for node_id, node_config in flow_config.steps.items():
                input_parameters = node_config.params
                _, output_parameters = await NodeManager.get_node_params(node_config.node)
                parameters = {
                    "input_parameters": input_parameters,
                    "output_parameters": Slot(output_parameters).extract_type_desc_from_schema(),
                }

                node_item = NodeItem(
                    stepId=node_id,
                    nodeId=node_config.node,
                    name=node_config.name,
                    description=node_config.description,
                    callId=node_config.type,
                    parameters=parameters,
                    position=PositionItem(x=node_config.pos.x, y=node_config.pos.y),
                )
                flow_item.nodes.append(node_item)

            for edge_config in flow_config.edges:
                edge_from = edge_config.edge_from
                branch_id = ""
                tmp_list = edge_config.edge_from
                if len(tmp_list) == 0 or len(tmp_list) > FLOW_SPLIT_LEN:
                    logger.error("[FlowManager] Flow中边的格式错误")
                    continue
                if len(tmp_list) == FLOW_SPLIT_LEN:
                    edge_from = tmp_list[0]
                    branch_id = tmp_list[1]
                flow_item.edges.append(
                    EdgeItem(
                        edgeId=edge_config.id,
                        sourceNode=edge_from,
                        targetNode=edge_config.edge_to,
                        type=edge_config.edge_type.value if edge_config.edge_type else EdgeType.NORMAL.value,
                        branchId=branch_id,
                    ),
                )
            return flow_item


    @staticmethod
    async def is_flow_config_equal(flow_config_1: Flow, flow_config_2: Flow) -> bool:
        """
        比较两个流配置是否相等

        :param flow_config_1: 流配置1
        :param flow_config_2: 流配置2
        :return: 如果相等则返回True，否则返回False
        """
        # 基本属性比较
        if len(flow_config_1.steps) != len(flow_config_2.steps):
            return False
        if len(flow_config_1.edges) != len(flow_config_2.edges):
            return False

        # 将steps转换为列表并排序
        step_list_1 = []
        for step in flow_config_1.steps.values():
            step_tuple = (
                step.node,
                step.type,
                step.description,
                tuple(sorted((k, str(v)) for k, v in step.params.items())),
            )
            step_list_1.append(step_tuple)

        step_list_2 = []
        for step in flow_config_2.steps.values():
            step_tuple = (
                step.node,
                step.type,
                step.description,
                tuple(sorted((k, str(v)) for k, v in step.params.items())),
            )
            step_list_2.append(step_tuple)

        # 排序后比较
        if sorted(step_list_1) != sorted(step_list_2):
            return False

        # 将edges转换为列表并排序
        edge_list_1 = [(edge.edge_from, edge.edge_to) for edge in flow_config_1.edges]
        edge_list_2 = [(edge.edge_from, edge.edge_to) for edge in flow_config_2.edges]

        return sorted(edge_list_1) == sorted(edge_list_2)


    @staticmethod
    async def put_flow_by_app_and_flow_id(
        app_id: uuid.UUID, flow_id: str, flow_item: FlowItem,
    ) -> None:
        """
        存储/更新flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param flow_item: 流的item
        """
        # 检查应用是否存在
        async with postgres.session() as session:
            app_record = (await session.scalars(
                select(App.id).where(
                    App.id == app_id,
                ),
            )).one_or_none()
            if app_record is None:
                err = f"[FlowManager] 应用 {app_id} 不存在"
                logger.error(err)
                raise ValueError(err)

            # Flow模版
            if not flow_item.basic_config:
                err = "[FlowManager] basic_config is required"
                logger.error(err)
                raise ValueError(err)

            flow_config = Flow(
                name=flow_item.name,
                description=flow_item.description,
                checkStatus=flow_item.check_status,
                basicConfig=flow_item.basic_config,
                steps={},
                edges=[],
            )
            # 增加Flow实际使用的节点
            for node_item in flow_item.nodes:
                flow_config.steps[node_item.step_id] = Step(
                    type=node_item.call_id,
                    node=node_item.node_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=node_item.position,
                    params=node_item.parameters.get("input_parameters", {}),
                )
            # 使用固定格式把边存入yaml中
            for edge_item in flow_item.edges:
                edge_from = edge_item.source_branch
                if edge_item.branch_id:
                    edge_from = edge_from + "." + edge_item.branch_id
                edge_config = Edge(
                    id=edge_item.edge_id,
                    edge_from=edge_from,
                    edge_to=edge_item.target_branch,
                    edge_type=EdgeType(edge_item.type) if edge_item.type else EdgeType.NORMAL,
                )
                flow_config.edges.append(edge_config)

            # 检查是否是修改动作；检查修改前后是否等价
            old_flow_config = await pool.flow_loader.load(app_id, flow_id)
            if old_flow_config and old_flow_config.checkStatus.debug:
                flow_config.checkStatus.debug = await FlowManager.is_flow_config_equal(old_flow_config, flow_config)

            await pool.flow_loader.save(app_id, flow_id, flow_config)


    @staticmethod
    async def delete_flow_by_app_and_flow_id(app_id: uuid.UUID, flow_id: str) -> None:
        """
        删除flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        """
        await pool.flow_loader.delete(app_id, flow_id)

        async with postgres.session() as session:
            key = f"flow/{flow_id}.yaml"
            await session.execute(
                delete(AppHashes).where(
                    and_(
                        AppHashes.appId == app_id,
                        AppHashes.filePath == key,
                    ),
                ),
            )
            # 同步更新metadata yaml文件中的hash值
            metadata = await pool.app_loader.read_metadata(app_id)
            if not isinstance(metadata, FlowAppMetadata):
                err = f"[FlowManager] 应用 {app_id} 不是Flow应用"
                logger.error(err)
                raise TypeError(err)

            # 从metadata的hashes中移除对应的flow文件hash
            if metadata.hashes and key in metadata.hashes:
                del metadata.hashes[key]

            metadata.flows = [flow for flow in metadata.flows if flow.id != flow_id]
            await pool.app_loader.save(metadata, app_id)


    @staticmethod
    async def update_flow_debug_by_app_and_flow_id(app_id: uuid.UUID, flow_id: str, *, debug: bool) -> bool:
        """
        更新flow的debug状态

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param debug: 是否开启debug
        :return: 是否更新成功
        """
        # 由于调用位置，从文件系统中获取Flow数据
        flow = await pool.flow_loader.load(app_id, flow_id)
        if flow is None:
            return False

        flow.checkStatus.debug = debug
        # 保存到文件系统
        await pool.flow_loader.save(app_id=app_id, flow_id=flow_id, flow=flow)
        return True
