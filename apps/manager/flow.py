"""flow Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Tuple, List
from pymongo import ASCENDING

from apps.constants import LOGGER
from apps.entities.flow import StepPos, Edge, Step, Flow
from apps.entities.pool import AppFlow
from apps.entities.flow_topology import ServiceItem, NodeMetaDataItem, FlowItem, NodeItem, EdgeItem, PositionItem
from apps.models.mongo import MongoDB
from apps.entities.enum_var import PermissionType


class FlowManager:

    @staticmethod
    async def validate_user_service_access(user_sub: str, service_id: str) -> bool:
        """验证用户对服务的访问权限

        :param user_sub: 用户唯一标识符
        :param service_id: 服务id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        service_collection = MongoDB.get_collection("service")

        try:
            service_collection = MongoDB.get_collection("service")
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
            query = {"$and": [{"_id": service_id},
                              {"$or": match_conditions},
                              {"favorites": user_sub}]}

            result = await service_collection.count_documents(query)
            return (result > 0)
        except Exception as e:
            LOGGER.error(f"Validate user service access failed due to: {e}")
            return False

    @staticmethod
    async def get_service_by_user_id(user_sub: str, page: int, page_size: int) -> Tuple[int, List[ServiceItem]]:
        """根据用户ID获取用户有执行权限且收藏的服务列表

        :param user_sub: 用户唯一标识符
        :param page: 当前页码
        :param page_size: 每页大小
        :return: 返回符合条件的服务总数和分页后的服务列表
        """
        service_collection = MongoDB.get_collection("service")
        try:
            skip_count = (page - 1) * page_size
            match_conditions = [
                {"author": user_sub},
                {"permissions.type": "PUBLIC"},
                {
                    "$and": [
                        {"permissions.type": "PROTECTED"},
                        {"permissions.users": user_sub}
                    ]
                }
            ]
            query = {"$and": [{"$or": match_conditions},
                              {"favorites": user_sub}]}

            total_services = await service_collection.count_documents(query)
            service_records_cursor = service_collection.find(
                query,
                skip=skip_count,
                limit=page_size,
                sort=[("created_at", ASCENDING)]
            )
            service_records = await service_records_cursor.to_list(length=None)
            service_items = [
                ServiceItem(
                    service_id=str(record["_id"]),
                    name=record["name"],
                    type=record["type"],
                    created_at=record["created_at"]
                )
                for record in service_records
            ]

            return total_services, service_items

        except Exception as e:
            LOGGER.error(f"Get service by user id failed due to: {e}")
            return None

    @staticmethod
    async def get_node_meta_datas_by_service_id(service_id: str) -> List[NodeMetaDataItem]:
        """serviceId获取service的接口数据，并将接口转换为节点元数据

        :param service_id: 服务id
        :return: 节点元数据的列表
        """
        node_pool_collection = MongoDB.get_collection("node")  # 获取节点集合
        try:
            cursor = node_pool_collection.find(
                {"service": service_id}).sort("created_at", ASCENDING)   # 查询指定service_id的所有node_poool

            nodes_meta_data_items = []
            async for node_pool_record in cursor:
                # 将每个node_pool换成NodeMetaDataItem实例
                node_meta_data_item = NodeMetaDataItem(
                    api_id=node_pool_record["id"],
                    name=node_pool_record['name'],
                    type=node_pool_record['type'],
                    description=node_pool_record['description'],
                    parameters_template=node_pool_record['parameters_template'],
                    editable=True,
                    created_at=node_pool_record['created_at']
                )
                nodes_meta_data_items.append(node_meta_data_item)

            return nodes_meta_data_items

        except Exception as e:
            LOGGER.error(
                f"Get node metadatas by service_id failed due to: {e}")
            return None

    @staticmethod
    async def get_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> Tuple[FlowItem, PositionItem]:
        """通过appId flowId获取flow config的路径和focus，并通过flow config的路径获取flow config，并将其转换为flow item。

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的item和用户在这个流上的视觉焦点
        """
        try:
            flow_collection = MongoDB.get_collection("app")
            flow_record = await flow_collection.aggregate([
                {"$match": {"_id": app_id, "flows._id": flow_id}},
                {"$unwind": "$flows"},
                {"$match": {"flows._id": flow_id}},
                {"$limit": 1},
            ]).to_list(length=1)
        except Exception as e:
            LOGGER.error(
                f"Get flow by app_id and flow_id failed due to: {e}")
            return None
        if flow_record:
            flow_config = await get_flow_config(app_id, flow_id)
            if not flow_config:
                LOGGER.error(
                    "Get flow config by app_id and flow_id failed")
                return None
            focus_point = flow_record["focus_point"]
            flow_item = FlowItem(
                flow_id=flow_id,
                name=flow_config.name,
                description=flow_config.description,
                enable=True,
                editable=True,
                nodes=[],
                edeges=[]
            )
            for node_config in flow_config.steps:
                node_item = NodeItem(
                    node_id=node_config.node_id,
                    app_id=node_config.node,
                    name=node_config.name,
                    description=node_config.description,
                    enable=True,
                    editable=True,
                    type=node_config.type,
                    parameters=node_config.params,
                    position=PositionItem(
                        x=node_config.position.x, y=node_config.position.y)
                )
                flow_item.nodes.append(node_item)

            for edge_config in flow_config.edges:
                tmp_list = edge_config.edge_from.split('.')
                branch_id = tmp_list[1] if len(tmp_list) > 2 else ''
                flow_item.edeges.append(EdgeItem(
                    edge_id=edge_config.id,
                    source_node=edge_config.edge_from,
                    target_node=edge_config.edge_to,
                    type=edge_config.type.value,
                    branch_id=branch_id,
                ))
                flow_item.nodes.append(node_item)
            return (flow_item, focus_point)
        return None

    @staticmethod
    async def put_flow_by_app_and_flow_id(app_id: str, flow_id: str, flow_item: FlowItem, focus_point: PositionItem) -> str:
        """存储/更新flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param flow_item: 流的item
        :return: 流的id
        """
        try:
            flow_collection = MongoDB.get_collection("app")
            flow_record = await flow_collection.aggregate([
                {"$match": {"_id": app_id, "flows._id": flow_id}},
                {"$unwind": "$flows"},
                {"$match": {"flows._id": flow_id}},
                {"$limit": 1},
            ]).to_list(length=1)
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
                    node=node_item.api_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=StepPos(x=node_item.position.x,
                                y=node_item.position.y),
                    params=node_item.parameters
                )
                flow_config.steps.append(edge_config)
            for edge_item in flow_item.edeges:
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
            if flow_record:
                result = await update_flow_config(app_id, flow_id, flow_config)
                if not result:
                    LOGGER.error(f"Update flow config failed")
                    return None
                app_collection = await MongoDB.get_collection("app")
                result = await app_collection.update_one(
                    {'_id': app_id},
                    {
                        '$set': {
                            'flows.$[flow].focus_point': focus_point
                        }
                    },
                    array_filters=[{'flow._id': flow_id}]
                )
                if result.modified_count > 0:
                    return flow_id
                else:
                    return None
            else:
                new_path = await add_flow_config(app_id, flow_id, flow_config)
                if not new_path:
                    LOGGER.error(f"Add flow config failed")
                    return None
                new_flow = AppFlow(
                    id=flow_id,
                    name=flow_item.name,
                    description=flow_item.description,
                    path=new_path,
                    focus_point=PositionItem(x=focus_point.x, y=focus_point.y),
                )
                result = await app_collection.update_one(
                    {'_id': app_id},
                    {
                        '$push': {
                            'flows': new_flow.model_dump(by_alias=True)
                        }
                    }
                )
                if result.modified_count > 0:
                    return flow_id
                else:
                    return None
        except Exception as e:
            LOGGER.error(
                f"Put flow by app_id and flow_id failed due to: {e}")
            return flow_id

    @staticmethod
    async def delete_flow_by_app_and_flow_id(app_id: str, flow_id: str) -> str:
        """删除flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :return: 流的id
        """

        try:
            result = await delete_flow_config(app_id, flow_id)
            if not result:
                LOGGER.error(f"Delete flow config failed")
                return None
            app_pool_collection = await MongoDB.get_collection("app")  # 获取集合

            # 执行删除操作，从指定的AppPool文档中移除匹配的AppFlow
            result = await app_pool_collection.update_one(
                {'_id': app_id},  # 查询条件，找到要更新的AppPool文档
                {
                    '$pull': {
                        'flows': {'id': flow_id}  # 假设'flows'数组中每个对象都有'id'字段
                    }
                }
            )

            if result.modified_count > 0:
                return flow_id
            else:
                return None
        except Exception as e:
            LOGGER.error(
                f"Delete flow by app_id and flow_id failed due to: {e}")
            return None
