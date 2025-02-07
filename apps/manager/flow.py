"""flow Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Tuple, List
from pymongo import ASCENDING

from apps.constants import LOGGER
from apps.entities.flow import StepPos, Edge, Step, Flow, FlowConfig
from apps.entities.pool import AppFlow
from apps.entities.flow_topology import NodeServiceItem, NodeMetaDataItem, FlowItem, NodeItem, EdgeItem, PositionItem
from apps.models.mongo import MongoDB
from apps.entities.enum_var import PermissionType


class FlowManager:

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
            match_conditions = [
                {"author": user_sub},
                {"permissions.type": PermissionType.PUBLIC.value},
                {
                    "$and": [
                        {"permissions.type": PermissionType.PROTECTED.value},
                        {"permissions.users": user_sub}
                    ]
                }
            ]
            query = {"$and": [{"_id": node_pool_record["service_id"]},
                            {"$or": match_conditions}
                            ]}

            result = await service_collection.count_documents(query)
            return (result > 0)
        except Exception as e:
            LOGGER.error(f"Validate user node meta data access failed due to: {e}")
            return False
    @staticmethod
    async def get_node_meta_datas_by_service_id(service_id: str) -> List[NodeMetaDataItem]:
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
                node_meta_data_item = NodeMetaDataItem(
                    nodeMetaDataId=node_pool_record["_id"],
                    type=node_pool_record["call_id"],
                    name=node_pool_record['name'],
                    description=node_pool_record['description'],
                    editable=True,
                    createdAt=node_pool_record['created_at'],
                )
                nodes_meta_data_items.append(node_meta_data_item)

            return nodes_meta_data_items

        except Exception as e:
            LOGGER.error(
                f"Get node metadatas by service_id failed due to: {e}")
            return None
    async def get_service_by_user_id(user_sub: str) -> List[NodeServiceItem]:
        """通过user_id获取用户自己上传的、其他人公开的且收藏的、受保护且有权限访问并收藏的service

        :user_sub: 用户的唯一标识符
        :return: service的列表
        """
        service_collection = MongoDB.get_collection("service")
        try:
            match_conditions = [
                {"name": "系统"},
                {"author": user_sub},
                {
                    "$and": [
                        {"permissions.type": PermissionType.PUBLIC.value},
                        {"favorites": user_sub}
                    ]
                },
                {
                    "$and": [
                        {"permissions.type": PermissionType.PROTECTED.value},
                        {"permissions.users": user_sub},
                        {"favorites": user_sub}
                    ]
                }
            ]
            query = {"$or": match_conditions}

            service_records_cursor = service_collection.find(
                query,
                sort=[("created_at", ASCENDING)]
            )
            service_records = await service_records_cursor.to_list(length=None)
            service_items = [
                NodeServiceItem(
                    serviceId=record["_id"],
                    name=record["name"],
                    type="default",
                    nodeMetaDatas=[],
                    createdAt=record["created_at"]
                )
                for record in service_records
            ]
            for service_item in service_items:
                node_meta_datas = await FlowManager.get_node_meta_datas_by_service_id(service_item.service_id)
                if node_meta_datas is None:
                    node_meta_datas=[]
                service_item.node_meta_datas = node_meta_datas
            return service_items

        except Exception as e:
            LOGGER.error(f"Get service by user id failed due to: {e}")
            return None
    @staticmethod
    async def get_node_meta_data_by_node_meta_data_id(node_meta_data_id: str) -> NodeMetaDataItem:
        """通过node_meta_data_id获取对应的节点源数据信息

        :param node_meta_data_id: node_meta_data的id
        :return: node meta data id对应的节点源数据信息
        """
        node_pool_collection = MongoDB.get_collection("node")  # 获取节点集合
        try:
            node_pool_record = await node_pool_collection.find_one({"_id": node_meta_data_id})
            parameters_template = {
                    "input_schema": node_pool_record['params_schema'],
                    "output_schema": node_pool_record['output_schema']
                }
            node_meta_data=NodeMetaDataItem(
                nodeMetaDataId=node_pool_record["_id"],
                type=node_pool_record["call_id"],
                name=node_pool_record['name'],
                description=node_pool_record['description'],
                editable=True,
                parametersTemplate=parameters_template,
                createdAt=node_pool_record['created_at'],
            )
            return node_meta_data
        except Exception as e:
            LOGGER.error(f"获取节点元数据失败: {e}")
            return None
    @staticmethod
    async def get_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> Tuple[FlowItem, PositionItem]:
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
                {"_id": app_id, "flows._id": flow_id},
                {"flows.$": 1}  # 只返回 flows 数组中符合条件的第一个元素
            )

            # 获取结果列表，并限制长度为1，因为我们只期待一个结果
            app_records = await cursor.to_list(length=1)
            if len(app_records) == 0:
                return None
            app_record = app_records[0]
            if "flows" not in app_record.keys() or len(app_record["flows"]) == 0:
                return None
            flow_record = app_record["flows"][0]
        except Exception as e:
            LOGGER.error(
                f"Get flow by app_id and flow_id failed due to: {e}")
            return None
        if flow_record:
            flow_config_collection = MongoDB.get_collection("flow_config")
            flow_config_record = await flow_config_collection.find_one({"app_id": app_id, "flow_id": flow_id})
            if flow_config_record  is None or not flow_config_record.get("flow_config"):
                return None
            flow_config = flow_config_record['flow_config']
            if not flow_config:
                LOGGER.error(
                    "Get flow config by app_id and flow_id failed")
                return None
            focus_point = flow_record["focus_point"]
            flow_item = FlowItem(
                flowId=flow_id,
                name=flow_config['name'],
                description=flow_config['description'],
                enable=True,
                editable=True,
                nodes=[],
                edges=[],
                createdAt=flow_record["created_at"]
            )
            for node_config in flow_config['steps']:
                node_item = NodeItem(
                    nodeId=node_config['id'],
                    apiId=node_config['node'],
                    name=node_config['name'],
                    description=node_config['description'],
                    enable=True,
                    editable=True,
                    type=node_config['type'],
                    parameters=node_config['params'],
                    position=PositionItem(
                        x=node_config['pos']['x'], y=node_config['pos']['y'])
                )
                flow_item.nodes.append(node_item)

            for edge_config in flow_config['edges']:
                edge_from = edge_config['edge_from']
                branch_id = ''
                tmp_list = edge_config['edge_from'].split('.')
                if len(tmp_list)==0 or len(tmp_list)>=2:
                    LOGGER.error("edge from format error")
                    continue
                if len(tmp_list) == 2:
                    edge_from = tmp_list[0]
                    branch_id = tmp_list[1]
                flow_item.edges.append(EdgeItem(
                    edgeId=edge_config['id'],
                    sourceNode=edge_from,
                    targetNode=edge_config['edge_to'],
                    type=edge_config['edge_type'],
                    branchId=branch_id,
                ))
            return (flow_item, focus_point)
        return None

    @staticmethod
    async def put_flow_by_app_and_flow_id(
            app_id: str, flow_id: str, flow_item: FlowItem, focus_point: PositionItem) -> str:
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
                {"flows.$": 1}
            )
            app_records = await cursor.to_list(length=1)
            flow_record = None
            if len(app_records) != 0:
                app_record = app_records[0]
                if "flows" in app_record.keys() and len(app_record["flows"]) != 0:
                    flow_record = app_record["flows"][0]
        except Exception as e:
            LOGGER.error(
                f"Get flow by app_id and flow_id failed due to: {e}")
            return None
        try:
            flow_config = Flow(
                name=flow_item.name,
                description=flow_item.description,
                steps=[],
                edges=[],
            )
            for node_item in flow_item.nodes:
                edge_config = Step(
                    id=node_item.node_id,
                    type=node_item.type,
                    node=node_item.api_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=StepPos(x=node_item.position.x,
                                y=node_item.position.y),
                    params=node_item.parameters
                )
                flow_config.steps.append(edge_config)
            for edge_item in flow_item.edges:
                edge_from = edge_item.source_node
                if edge_item.branch_id:
                    edge_from = edge_from+'.'+edge_item.branch_id
                edge_config = Edge(
                    id=edge_item.edge_id,
                    edge_from=edge_from,
                    edge_to=edge_item.target_node,
                    edge_type=edge_item.type
                )
                flow_config.edges.append(edge_config)
            flow_config = FlowConfig(app_id=app_id, flow_id=flow_id, flow_config=flow_config)
            try:
                flow_config_collection = MongoDB.get_collection("flow_config")
                await flow_config_collection.update_one(
                    {"app_id": app_id, "flow_id": flow_id},
                    {"$set": flow_config.dict()},
                    upsert=True  # 如果没有找到匹配的文档，则插入新文档
                )
            except Exception as e:
                LOGGER.error(f"Error updating flow config due to: {e}")
                return None
            if flow_record:
                app_collection = MongoDB.get_collection("app")
                result = await app_collection.find_one_and_update(
                    {'_id': app_id},
                    {
                        '$set': {
                            'flows.$[element].focus_point': focus_point.model_dump(by_alias=True)
                        }
                    },
                    array_filters=[{'element._id': flow_id}],
                    return_document=True  # 返回更新后的文档
                )
                if result is None:
                    LOGGER.error("Update flow failed")
                    return None
                return result
            else:
                new_flow = AppFlow(
                    _id=flow_id,
                    name=flow_item.name,
                    description=flow_item.description,
                    path="",
                    focus_point=PositionItem(x=focus_point.x, y=focus_point.y),
                )
                app_collection = MongoDB.get_collection("app")
                result = await app_collection.find_one_and_update(
                    {'_id': app_id},
                    {
                        '$push': {
                            'flows': new_flow.model_dump(by_alias=True)
                        }
                    }
                )
                if result is None:
                    LOGGER.error("Add flow failed")
                    return None
                return flow_item
        except Exception as e:
            LOGGER.error(
                f"Put flow by app_id and flow_id failed due to: {e}")
            return None

    async def delete_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> str:
        """删除flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的id
        """

        try:
            flow_config_collection = MongoDB.get_collection("flow_config")
            result = await flow_config_collection.delete_one({"app_id": app_id, "flow_id": flow_id})
            if result.deleted_count == 0:
                LOGGER.error("Delete flow config failed")
                return None
            app_pool_collection = MongoDB.get_collection("app")  # 获取集合

            result = await app_pool_collection.find_one_and_update(
                {'_id': app_id}, 
                {
                    '$pull': {
                        'flows': {'_id': flow_id}
                    }
                }
            )
            if result is None:
                LOGGER.error("Delete flow from app pool failed")
                return None
            return flow_id
        except Exception as e:
            LOGGER.error(
                f"Delete flow by app_id and flow_id failed due to: {e}")
            return None
