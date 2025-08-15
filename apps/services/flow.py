# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""flow Manager"""

import logging

from pymongo import ASCENDING

from apps.common.mongo import MongoDB
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.slot.slot import Slot
from apps.schemas.collection import User
from apps.schemas.enum_var import EdgeType, PermissionType, LanguageType
from apps.schemas.flow import Edge, Flow, Step
from apps.schemas.flow_topology import (
    EdgeItem,
    FlowItem,
    NodeItem,
    NodeMetaDataItem,
    NodeServiceItem,
    PositionItem,
)
from apps.scheduler.pool.pool import Pool
from apps.services.node import NodeManager
logger = logging.getLogger(__name__)


class FlowManager:
    """Flow相关操作"""

    @staticmethod
    async def validate_user_node_meta_data_access(user_sub: str, node_meta_data_id: str) -> bool:
        """
        验证用户对服务的访问权限

        :param user_sub: 用户唯一标识符
        :param service_id: 服务id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        node_pool_collection = MongoDB().get_collection("node")
        service_collection = MongoDB().get_collection("service")

        try:
            node_pool_record = await node_pool_collection.find_one({"_id": node_meta_data_id})
            if node_pool_record is None:
                logger.error("[FlowManager] 节点元数据 %s 不存在", node_meta_data_id)
                return False
            match_conditions = [
                {"author": user_sub},
                {"permission.type": PermissionType.PUBLIC.value},
                {
                    "$and": [
                        {"permission.type": PermissionType.PROTECTED.value},
                        {"permission.users": user_sub},
                    ],
                },
            ]
            query = {
                "$and": [
                    {"_id": node_pool_record["service_id"]},
                    {"$or": match_conditions},
                ],
            }

            result = await service_collection.count_documents(query)
        except Exception:
            logger.exception("[FlowManager] 验证用户对服务的访问权限失败")
            return False
        else:
            return (result > 0)

    @staticmethod
    async def get_node_id_by_service_id(
        service_id: str, language: LanguageType = LanguageType.CHINESE
    ) -> list[NodeMetaDataItem] | None:
        """
        serviceId获取service的接口数据，并将接口转换为节点元数据

        :param service_id: 服务id
        :return: 节点元数据的列表
        """
        node_pool_collection = MongoDB().get_collection("node")  # 获取节点集合
        try:
            cursor = node_pool_collection.find({"service_id": service_id}).sort("created_at", ASCENDING)

            nodes_meta_data_items = []
            async for node_pool_record in cursor:
                params_schema, output_schema = await NodeManager.get_node_params(node_pool_record["_id"])
                try:
                    # TODO: 由于现在没有动态表单，所以暂时使用Slot的create_empty_slot方法
                    parameters = {
                        "input_parameters": Slot(params_schema).create_empty_slot(),
                        "output_parameters": Slot(output_schema).extract_type_desc_from_schema(),
                    }
                except Exception:
                    logger.exception("[FlowManager] generate_from_schema 失败")
                    continue

                if service_id == "":
                    call_class: type[BaseModel] = await Pool().get_call(node_pool_record["_id"])
                    call_class.language = language
                    node_name = call_class.info().name
                    node_description = call_class.info().description
                else:
                    node_name = node_pool_record["name"]
                    node_description = node_pool_record["description"]

                node_meta_data_item = NodeMetaDataItem(
                    nodeId=node_pool_record["_id"],
                    callId=node_pool_record["call_id"],
                    name=node_name,
                    description=node_description,
                    editable=True,
                    createdAt=node_pool_record["created_at"],
                    parameters=parameters,  # 添加 parametersTemplate 参数
                )
                nodes_meta_data_items.append(node_meta_data_item)
        except Exception:
            logger.exception("[FlowManager] 获取节点元数据失败")
            return None
        else:
            return nodes_meta_data_items

    @staticmethod
    async def get_service_by_user_id(
        user_sub: str, language: LanguageType = LanguageType.CHINESE
    ) -> list[NodeServiceItem] | None:
        """
        通过user_id获取用户自己上传的、其他人公开的且收藏的、受保护且有权限访问并收藏的service

        :user_sub: 用户的唯一标识符
        :return: service的列表
        """
        service_collection = MongoDB().get_collection("service")
        user_collection = MongoDB().get_collection("user")
        try:
            db_result = await user_collection.find_one({"_id": user_sub})
            user = User.model_validate(db_result)
            if user is None:
                logger.error("[FlowManager] 用户 %s 不存在或数据损坏", user_sub)
                return None
            # 获取用户收藏的服务列表
            fav_services = user.fav_services
            logger.info("[FlowManager] 用户 %s 收藏的服务列表: %s", user_sub, fav_services)
            match_conditions = [
                {"author": user_sub},
                {
                    "$and": [
                        {"permission.type": PermissionType.PUBLIC.value},
                        {"_id": {"$in": fav_services}},
                    ],
                },
                {
                    "$and": [
                        {"permission.type": PermissionType.PROTECTED.value},
                        {"permission.users": {"$in": [user_sub]}},
                        {"_id": {"$in": fav_services}},
                    ],
                },
            ]
            query = {"$or": match_conditions}
            service_records_cursor = service_collection.find(
                query,
                sort=[("created_at", ASCENDING)],
            )
            service_records = await service_records_cursor.to_list(length=None)
            service_items = [
                NodeServiceItem(
                    serviceId="",
                    name="系统" if language == LanguageType.CHINESE else "System",
                    type="system",
                    nodeMetaDatas=[],
                )
            ]
            service_items += [
                NodeServiceItem(
                    serviceId=record["_id"],
                    name=record["name"],
                    type="default",
                    nodeMetaDatas=[],
                    createdAt=str(record["created_at"]),
                )
                for record in service_records
            ]
            for service_item in service_items:
                node_meta_datas = await FlowManager.get_node_id_by_service_id(
                    service_item.service_id, language
                )
                if node_meta_datas is None:
                    node_meta_datas = []
                service_item.node_meta_datas = node_meta_datas
        except Exception:
            logger.exception("[FlowManager] 获取用户服务失败")
            return None
        else:
            return service_items

    @staticmethod
    async def get_node_meta_data_by_node_meta_data_id(node_meta_data_id: str) -> NodeMetaDataItem | None:
        """
        通过node_meta_data_id获取对应的节点源数据信息

        :param node_meta_data_id: node_meta_data的id
        :return: node meta data id对应的节点源数据信息
        """
        node_pool_collection = MongoDB().get_collection("node")  # 获取节点集合
        try:
            node_pool_record = await node_pool_collection.find_one({"_id": node_meta_data_id})
            if node_pool_record is None:
                logger.error("[FlowManager] 节点元数据 %s 不存在", node_meta_data_id)
                return None
            parameters = {
                "input_parameters": node_pool_record["params_schema"],
                "output_parameters": node_pool_record["output_schema"],
            }
            return NodeMetaDataItem(
                nodeId=node_pool_record["_id"],
                callId=node_pool_record["call_id"],
                name=node_pool_record["name"],
                description=node_pool_record["description"],
                editable=True,
                parameters=parameters,
                createdAt=node_pool_record["created_at"],
            )
        except Exception:
            logger.exception("[FlowManager] 获取节点元数据失败")
            return None

    @staticmethod
    async def get_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> FlowItem | None:  # noqa: C901, PLR0911, PLR0912
        """
        通过appId flowId获取flow config的路径和focus，并通过flow config的路径获取flow config，并将其转换为flow item。

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的item和用户在这个流上的视觉焦点
        """
        try:
            app_collection = MongoDB().get_collection("app")
            app_record = await app_collection.find_one({"_id": app_id})
            if app_record is None:
                logger.error("[FlowManager] 应用 %s 不存在", app_id)
                return None
            cursor = app_collection.find(
                {"_id": app_id, "flows.id": flow_id},
                {"flows.$": 1},  # 只返回 flows 数组中符合条件的第一个元素
            )
            # 获取结果列表，并限制长度为1，因为我们只期待一个结果
            app_records = await cursor.to_list(length=1)
            if len(app_records) == 0:
                return None
            app_record = app_records[0]
            if "flows" not in app_record or len(app_record["flows"]) == 0:
                return None
            for flow in app_record["flows"]:
                if flow["id"] == flow_id:
                    flow_record = flow
                    break
            if flow_record is None:
                return None
        except Exception:
            logger.exception("[FlowManager] 获取流失败")
            return None

        try:
            flow_config = await FlowLoader().load(app_id, flow_id)
            if not flow_config:
                logger.error("[FlowManager] 获取流配置失败")
                return None
            focus_point = flow_config.focus_point or PositionItem(x=0, y=0)
            flow_item = FlowItem(
                flowId=flow_id,
                name=flow_config.name,
                description=flow_config.description,
                enable=True,
                editable=True,
                nodes=[],
                edges=[],
                focusPoint=focus_point,
                connectivity=flow_config.connectivity,
                debug=flow_config.debug,
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
                    enable=True,
                    editable=True,
                    callId=node_config.type,
                    parameters=parameters,
                    position=PositionItem(
                        x=node_config.pos.x, y=node_config.pos.y),
                )
                flow_item.nodes.append(node_item)

            for edge_config in flow_config.edges:
                edge_from = edge_config.edge_from
                branch_id = ""
                tmp_list = edge_config.edge_from.split(".")
                if len(tmp_list) == 0 or len(tmp_list) > 2:
                    logger.error("[FlowManager] Flow中边的格式错误")
                    continue
                if len(tmp_list) == 2:
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
        except Exception:
            logger.exception("[FlowManager] 获取流失败")
            return None

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
        app_id: str,
        flow_id: str,
        flow_item: FlowItem,
    ) -> FlowItem | None:
        """
        存储/更新flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param flow_item: 流的item
        :return: 流的id
        """
        try:
            app_collection = MongoDB().get_collection("app")
            app_record = await app_collection.find_one({"_id": app_id})
            if app_record is None:
                logger.error("[FlowManager] 应用 %s 不存在", app_id)
                return None
        except Exception:
            logger.exception("[FlowManager] 获取流失败")
            return None
        try:
            flow_config = Flow(
                name=flow_item.name,
                description=flow_item.description,
                steps={},
                edges=[],
                focus_point=flow_item.focus_point,
                connectivity=flow_item.connectivity,
                debug=flow_item.debug,
            )
            for node_item in flow_item.nodes:
                flow_config.steps[node_item.step_id] = Step(
                    type=node_item.call_id,
                    node=node_item.node_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=node_item.position,
                    params=node_item.parameters.get("input_parameters", {}),
                )
            for edge_item in flow_item.edges:
                edge_from = edge_item.source_node
                if edge_item.branch_id:
                    edge_from = edge_from + "." + edge_item.branch_id
                edge_config = Edge(
                    id=edge_item.edge_id,
                    edge_from=edge_from,
                    edge_to=edge_item.target_node,
                    edge_type=EdgeType(edge_item.type) if edge_item.type else EdgeType.NORMAL,
                )
                flow_config.edges.append(edge_config)

            flow_loader = FlowLoader()
            old_flow_config = await flow_loader.load(app_id, flow_id)

            if old_flow_config is None:
                error_msg = f"[FlowManager] 流 {flow_id} 不存在；可能为新创建"
                logger.error(error_msg)
            elif old_flow_config.debug:
                flow_config.debug = await FlowManager.is_flow_config_equal(old_flow_config, flow_config)
            else:
                flow_config.debug = False
            await flow_loader.save(app_id, flow_id, flow_config)
        except Exception:
            logger.exception("[FlowManager] 存储/更新流失败")
            return None
        else:
            return flow_item

    @staticmethod
    async def delete_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> str | None:
        """
        删除flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的id
        """
        try:

            app_collection = MongoDB().get_collection("app")
            key = f"flow/{flow_id}.yaml"
            await app_collection.update_one({"_id": app_id}, {"$unset": {f"hashes.{key}": ""}})
            await app_collection.update_one({"_id": app_id}, {"$pull": {"flows": {"id": flow_id}}})

            result = await FlowLoader().delete(app_id, flow_id)

            if result is None:
                logger.error("[FlowManager] 删除流失败")
                return None
        except Exception:
            logger.exception("[FlowManager] 删除流失败")
            return None
        else:
            return flow_id

    @staticmethod
    async def update_flow_debug_by_app_and_flow_id(app_id: str, flow_id: str, *, debug: bool) -> bool:
        """
        更新flow的debug状态

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param debug: 是否开启debug
        :return: 是否更新成功
        """
        try:
            flow_loader = FlowLoader()
            flow = await flow_loader.load(app_id, flow_id)
            if flow is None:
                return False
            flow.debug = debug
            await flow_loader.save(app_id=app_id, flow_id=flow_id, flow=flow)
        except Exception:
            logger.exception("[FlowManager] 更新流debug状态失败")
            return False
        else:
            return True
