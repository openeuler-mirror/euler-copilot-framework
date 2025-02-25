"""flow Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from pymongo import ASCENDING

from apps.constants import LOGGER
from apps.entities.appcenter import AppLink
from apps.entities.enum_var import EdgeType, MetadataType, PermissionType
from apps.entities.flow import AppMetadata, Edge, Flow, Permission, Step, StepPos
from apps.entities.flow_topology import (
    EdgeItem,
    FlowItem,
    NodeItem,
    NodeMetaDataItem,
    NodeServiceItem,
    PositionItem,
)
from apps.entities.pool import AppFlow, AppPool
from apps.manager.node import NodeManager
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.app import AppLoader
from apps.scheduler.pool.loader.flow import FlowLoader


class FlowManager:
    """Flow相关操作"""

    @staticmethod
    async def validate_user_node_meta_data_access(user_sub: str, node_meta_data_id: str) -> bool:
        """验证用户对服务的访问权限

        :param user_sub: 用户唯一标识符
        :param service_id: 服务id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        node_pool_collection = MongoDB.get_collection("node")
        service_collection = MongoDB.get_collection("service")

        try:
            node_pool_record = await node_pool_collection.find_one({"_id": node_meta_data_id})
            if node_pool_record is None:
                LOGGER.error(f"节点元数据{node_meta_data_id}不存在")
                return False
            match_conditions = [
                {"author": user_sub},
                {"permissions.type": PermissionType.PUBLIC.value},
                {
                    "$and": [
                        {"permissions.type": PermissionType.PROTECTED.value},
                        {"permissions.users": user_sub},
                    ],
                },
            ]
            query = {"$and": [
                {"_id": node_pool_record["service_id"]},
                {"$or": match_conditions},
            ]}

            result = await service_collection.count_documents(query)
            return (result > 0)
        except Exception as e:
            LOGGER.error(f"Validate user node meta data access failed due to: {e}")
            return False

    @staticmethod
    async def get_node_meta_datas_by_service_id(service_id: str) -> Optional[list[NodeMetaDataItem]]:
        """serviceId获取service的接口数据，并将接口转换为节点元数据

        :param service_id: 服务id
        :return: 节点元数据的列表
        """
        node_pool_collection = MongoDB.get_collection("node")  # 获取节点集合
        try:
            cursor = node_pool_collection.find(
                {"service_id": service_id}).sort("created_at", ASCENDING)

            nodes_meta_data_items = []
            async for node_pool_record in cursor:
                params_schema, output_schema = await NodeManager.get_node_params(node_pool_record["_id"])
                parameters = {
                    "input_parameters": params_schema,
                    "output_parameters": output_schema,
                }
                node_meta_data_item = NodeMetaDataItem(
                    nodeMetaDataId=node_pool_record["_id"],
                    type=node_pool_record["call_id"],
                    name=node_pool_record["name"],
                    description=node_pool_record["description"],
                    editable=True,
                    createdAt=node_pool_record["created_at"],
                    parameters=parameters,  # 添加 parametersTemplate 参数
                )
                nodes_meta_data_items.append(node_meta_data_item)
            return nodes_meta_data_items
        except Exception as e:
            LOGGER.error(
                f"Get node metadatas by service_id failed due to: {e}")
            return None

    @staticmethod
    async def get_service_by_user_id(user_sub: str) -> Optional[list[NodeServiceItem]]:
        """通过user_id获取用户自己上传的、其他人公开的且收藏的、受保护且有权限访问并收藏的service

        :user_sub: 用户的唯一标识符
        :return: service的列表
        """
        service_collection = MongoDB.get_collection("service")
        user_collection = MongoDB.get_collection("user")
        try:
            user_record = await user_collection.find_one({"_id": user_sub}, {"fav_services": 1, "_id": 0})
            fav_services = []
            if user_record:
                fav_services = user_record.get("fav_services", [])
            else:
                return []
            match_conditions = [
                {"author": user_sub},
                {
                    "$and": [
                        {"permissions.type": PermissionType.PUBLIC.value},
                        {"_id": {"$in": fav_services}},
                    ],
                },
                {
                    "$and": [
                        {"permissions.type": PermissionType.PROTECTED.value},
                        {"permissions.users": user_sub},
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
                    name="系统",
                    type="system",
                    nodeMetaDatas=[]
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
                node_meta_datas = await FlowManager.get_node_meta_datas_by_service_id(service_item.service_id)
                if node_meta_datas is None:
                    node_meta_datas = []
                service_item.node_meta_datas = node_meta_datas
            return service_items

        except Exception as e:
            LOGGER.error(f"Get service by user id failed due to: {e}")
            return None

    @staticmethod
    async def get_node_meta_data_by_node_meta_data_id(node_meta_data_id: str) -> Optional[NodeMetaDataItem]:
        """通过node_meta_data_id获取对应的节点源数据信息

        :param node_meta_data_id: node_meta_data的id
        :return: node meta data id对应的节点源数据信息
        """
        node_pool_collection = MongoDB.get_collection("node")  # 获取节点集合
        try:
            node_pool_record = await node_pool_collection.find_one({"_id": node_meta_data_id})
            if node_pool_record is None:
                LOGGER.error(f"节点元数据{node_meta_data_id}不存在")
                return None
            parameters = {
                "input_parameters": node_pool_record["params_schema"],
                "output_parameters": node_pool_record["output_schema"],
            }
            return NodeMetaDataItem(
                nodeMetaDataId=node_pool_record["_id"],
                type=node_pool_record["call_id"],
                name=node_pool_record["name"],
                description=node_pool_record["description"],
                editable=True,
                parameters=parameters,
                createdAt=node_pool_record["created_at"],
            )
        except Exception as e:
            LOGGER.error(f"获取节点元数据失败: {e}")
            return None

    @staticmethod
    async def get_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> Optional[tuple[FlowItem, PositionItem]]:
        """通过appId flowId获取flow config的路径和focus，并通过flow config的路径获取flow config，并将其转换为flow item。

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的item和用户在这个流上的视觉焦点
        """
        try:
            app_collection = MongoDB.get_collection("app")
            app_record = await app_collection.find_one({"_id": app_id})
            if app_record is None:
                LOGGER.error(f"应用{app_id}不存在")
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
            flow_record = app_record["flows"][0]
        except Exception as e:
            LOGGER.error(
                f"Get flow by app_id and flow_id failed due to: {e}")
            return None
        try:
            if flow_record:
                flow_config = await FlowLoader().load(app_id, flow_id)
                if not flow_config:
                    LOGGER.error(
                        "Get flow config by app_id and flow_id failed")
                    return None
                focus_point = flow_record["focus_point"]
                flow_item = FlowItem(
                    flowId=flow_id,
                    name=flow_config.name,
                    description=flow_config.description,
                    enable=True,
                    editable=True,
                    nodes=[],
                    edges=[],
                    debug=flow_config.debug,
                )
                for node_id, node_config in flow_config.steps.items():
                    node_item = NodeItem(
                        nodeId=node_id,
                        nodeMetaDataId=node_config.node,
                        name=node_config.name,
                        description=node_config.description,
                        enable=True,
                        editable=True,
                        type=node_config.type,
                        parameters=node_config.params,
                        position=PositionItem(
                            x=node_config.pos.x, y=node_config.pos.y),
                    )
                    flow_item.nodes.append(node_item)

                for edge_config in flow_config.edges:
                    edge_from = edge_config.edge_from
                    branch_id = ""
                    tmp_list = edge_config.edge_from.split(".")
                    if len(tmp_list) == 0 or len(tmp_list) > 2:
                        LOGGER.error("edge from format error")
                        continue
                    if len(tmp_list) == 2:
                        edge_from = tmp_list[0]
                        branch_id = tmp_list[1]
                    flow_item.edges.append(EdgeItem(
                        edgeId=edge_config.id,
                        sourceNode=edge_from,
                        targetNode=edge_config.edge_to,
                        type=edge_config.edge_type.value if edge_config.edge_type else EdgeType.NORMAL.value,
                        branchId=branch_id,
                    ))
                return (flow_item, focus_point)
            return None
        except Exception as e:
            LOGGER.error(
                f"Get flow by app_id and flow_id failed due to: {e}")
            return None

    @staticmethod
    async def put_flow_by_app_and_flow_id(
            app_id: str, flow_id: str, flow_item: FlowItem, focus_point: PositionItem) -> Optional[FlowItem]:
        """存储/更新flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param flow_item: 流的item
        :return: 流的id
        """
        try:
            app_collection = MongoDB.get_collection("app")
            app_record = await app_collection.find_one({"_id": app_id})
            if app_record is None:
                LOGGER.error(f"应用{app_id}不存在")
                return None
            cursor = app_collection.find(
                {"_id": app_id, "flows._id": flow_id},
                {"flows.$": 1},
            )
            app_records = await cursor.to_list(length=1)
            flow_record = None
            if len(app_records) != 0:
                app_record = app_records[0]
                if "flows" in app_record and len(app_record["flows"]) != 0:
                    flow_record = app_record["flows"][0]
        except Exception as e:
            LOGGER.error(
                f"Get flow by app_id and flow_id failed due to: {e}")
            return None
        try:
            flow_config = Flow(
                name=flow_item.name,
                description=flow_item.description,
                steps={},
                edges=[],
                debug=False,
            )
            for node_item in flow_item.nodes:
                flow_config.steps[node_item.node_id] = Step(
                    type=node_item.type,
                    node=node_item.node_meta_data_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=StepPos(x=node_item.position.x,
                                y=node_item.position.y),
                    params=node_item.parameters,
                )
            for edge_item in flow_item.edges:
                edge_from = edge_item.source_node
                if edge_item.branch_id:
                    edge_from = edge_from+"."+edge_item.branch_id
                edge_config = Edge(
                    id=edge_item.edge_id,
                    edge_from=edge_from,
                    edge_to=edge_item.target_node,
                    edge_type=EdgeType(edge_item.type) if edge_item.type else EdgeType.NORMAL,
                )
                flow_config.edges.append(edge_config)
            await FlowLoader().save(app_id, flow_id, flow_config)
            flow_config = await FlowLoader().load(app_id, flow_id)
            # 修改app内flow信息
            app_collection = MongoDB.get_collection("app")
            result = await app_collection.find_one({"_id": app_id})
            app_pool = AppPool.model_validate(result)
            metadata = AppMetadata(
                type=MetadataType.APP,
                id=app_pool.id,
                icon=app_pool.icon,
                name=app_pool.name,
                description=app_pool.description,
                version="1.0",
                author=app_pool.author,
                hashes=app_pool.hashes,
                published=app_pool.published,
                links=app_pool.links,
                first_questions=app_pool.first_questions,
                history_len=app_pool.history_len,
                permission=app_pool.permission,
                flows=app_pool.flows,
            )
            if flow_record:
                for flow in metadata.flows:
                    if flow.id == flow_id:
                        flow.name = flow_item.name
                        flow.description = flow_item.description
                        flow.path = ""
                        flow.focus_point = PositionItem(x=focus_point.x, y=focus_point.y)
            else:
                new_flow = AppFlow(
                    id=flow_id,
                    name=flow_item.name,
                    description=flow_item.description,
                    path="",
                    focus_point=PositionItem(x=focus_point.x, y=focus_point.y),
                )
                metadata.flows.append(new_flow)
            app_loader = AppLoader()
            await app_loader.save(metadata, app_id)
            if result is None:
                LOGGER.error("Add flow failed")
                return None
            return flow_item
        except Exception as e:
            LOGGER.error(
                f"Put flow by app_id and flow_id failed due to: {e}")
            return None

    @staticmethod
    async def delete_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> Optional[str]:
        """删除flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的id
        """
        try:
            result = await FlowLoader().delete(app_id, flow_id)
            # 修改app内flow信息
            app_collection = MongoDB.get_collection("app")
            result = await app_collection.find_one({"_id": app_id})
            app_pool = AppPool.model_validate(result)
            metadata = AppMetadata(
                type=MetadataType.APP,
                id=app_pool.id,
                icon=app_pool.icon,
                name=app_pool.name,
                description=app_pool.description,
                version="1.0",
                author=app_pool.author,
                hashes=app_pool.hashes,
                published=app_pool.published,
                links=app_pool.links,
                first_questions=app_pool.first_questions,
                history_len=app_pool.history_len,
                permission=app_pool.permission,
                flows=app_pool.flows,
            )
            for flow in metadata.flows:
                if flow.id == flow_id:
                    metadata.flows.remove(flow)
            app_loader = AppLoader()
            await app_loader.save(metadata, app_id)
            if result is None:
                LOGGER.error("Delete flow from app pool failed")
                return None
            return flow_id
        except Exception as e:
            LOGGER.error(
                f"Delete flow by app_id and flow_id failed due to: {e}")
            return None

    @staticmethod
    async def updata_flow_debug_by_app_and_flow_id(app_id: str, flow_id: str, debug: bool) -> bool:
        try:
            app_pool_collection = MongoDB.get_collection("app")
            result = await app_pool_collection.find_one(
                {"_id": app_id,"flows.id": flow_id}  # 使用关键字参数 array_filters
            )
            if result is None:
                LOGGER.error("Update flow debug from app pool failed")
                return False
            app_pool = AppPool(
                    _id=result["_id"],  # 使用 alias="_id" 自动映射
                    name=result.get("name", ""),
                    description=result.get("description", ""),
                    created_at=result.get("created_at", None),
                    author=result.get("author", ""),
                    icon=result.get("icon", ""),
                    published=result.get("published", False),
                    links=[AppLink(**link) for link in result.get("links", [])],
                    first_questions=result.get("first_questions", []),
                    history_len=result.get("history_len", 3),
                    permission=Permission(**result.get("permission", {})),
                    flows=[AppFlow(**flow) for flow in result.get("flows", [])],
                )
            metadata = AppMetadata(
                id=app_pool.id,
                name=app_pool.name,
                description=app_pool.description,
                author=app_pool.author,
                icon=app_pool.id,
                published=app_pool.published,
                links=app_pool.links,
                first_questions=app_pool.first_questions,
                history_len=app_pool.history_len,
                permission=app_pool.permission,
                flows=app_pool.flows,
                version="1.0",
            )
            for flows in metadata.flows:
                if flows.id == flow_id:
                    flows.debug = debug
            app_loader = AppLoader()
            await app_loader.save(metadata, app_id)
            flow_loader = FlowLoader()
            flow = await flow_loader.load(app_id, flow_id)
            if flow is None:
                return False
            flow.debug = debug
            await flow_loader.save(app_id=app_id,flow_id=flow_id,flow=flow)
            return True
        except Exception as e:
            LOGGER.error(f"Update flow debug from app pool failed: {e!s}")
            return False
