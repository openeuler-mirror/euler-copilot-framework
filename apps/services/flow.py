# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""flow Manager"""

import logging
from typing import Any

from pydantic import BaseModel, Field
from pymongo import ASCENDING

from apps.common.mongo import MongoDB
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.slot.slot import Slot
from apps.schemas.collection import User
from apps.schemas.enum_var import EdgeType, PermissionType, LanguageType
from apps.schemas.flow import Edge, Flow, Note, Step
from apps.schemas.flow_topology import (
    EdgeItem,
    FlowItem,
    NodeItem,
    NodeMetaDataItem,
    NodeServiceItem,
    NoteItem,
    PositionItem,
)
from apps.scheduler.pool.pool import Pool
from apps.services.node import NodeManager
from apps.scheduler.executor.step import StepExecutor

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
        node_pool_collection = MongoDB.get_collection("node")
        service_collection = MongoDB.get_collection("service")

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
        node_pool_collection = MongoDB.get_collection("node")  # 获取节点集合
        try:
            cursor = node_pool_collection.find(
                {"service_id": service_id}).sort("created_at", ASCENDING)

            nodes_meta_data_items = []
            async for node_pool_record in cursor:
                params_schema, output_schema = await NodeManager.get_node_params(node_pool_record["_id"])
                try:
                    # TODO: 由于现在没有动态表单，所以暂时使用Slot的create_empty_slot方法
                    # 对于循环节点，输出参数已经是扁平化格式，不需要再次处理
                    if node_pool_record["call_id"] in ["Loop"]:
                        output_parameters = output_schema
                    else:
                        output_parameters = Slot(
                            output_schema).extract_type_desc_from_schema()
                        # 如果输出参数是对象类型，直接使用 items 字段，去除顶层包装
                        # 这样 {type: 'object', items: {reply: {...}}} 会变成 {reply: {...}}
                        if isinstance(output_parameters, dict) and output_parameters.get("type") == "object" and "items" in output_parameters:
                            output_parameters = output_parameters["items"]

                    parameters = {
                        "input_parameters": Slot(params_schema).create_empty_slot(),
                        "output_parameters": output_parameters,
                    }
                except Exception:
                    logger.exception("[FlowManager] generate_from_schema 失败")
                    continue

                if service_id == "":
                    call_class: type[BaseModel] = await Pool().get_call(node_pool_record["_id"])
                    node_name = call_class.info(language).name
                    node_description = call_class.info(language).description
                else:
                    node_name = node_pool_record["name"]
                    node_description = node_pool_record["description"]

                node_meta_data_item = NodeMetaDataItem(
                    nodeId=node_pool_record["_id"],
                    callId=node_pool_record["call_id"],
                    name=node_name,
                    type=node_pool_record["type"],
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
        service_collection = MongoDB.get_collection("service")
        user_collection = MongoDB.get_collection("user")
        try:
            db_result = await user_collection.find_one({"_id": user_sub})
            user = User.model_validate(db_result)
            if user is None:
                logger.error("[FlowManager] 用户 %s 不存在或数据损坏", user_sub)
                return None
            # 获取用户收藏的服务列表
            fav_services = user.fav_services
            logger.info("[FlowManager] 用户 %s 收藏的服务列表: %s",
                        user_sub, fav_services)
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
                    type="plugin",  # 除了system固有节点，其余均为插件
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
        node_pool_collection = MongoDB.get_collection("node")  # 获取节点集合
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
            app_collection = MongoDB.get_collection("app")
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
                notes=[],
                focusPoint=focus_point,
                connectivity=flow_config.connectivity,
                debug=flow_config.debug,
            )
            for node_id, node_config in flow_config.steps.items():
                # 根据Call的controlled_output属性判断是否允许用户定义output parameters
                # TODO 两种处理分支应该有办法统一
                try:
                    call_cls = await StepExecutor.get_call_cls(node_config.type)
                    # 获取controlled_output属性值，默认为False
                    controlled_output = getattr(
                        call_cls, 'controlled_output', False)
                    # 如果是类字段而不是实例属性，需要从字段定义中获取默认值
                    if hasattr(call_cls, 'model_fields') and 'controlled_output' in call_cls.model_fields:
                        field_info = call_cls.model_fields['controlled_output']
                        controlled_output = getattr(
                            field_info, 'default', False)
                except Exception as e:
                    logger.warning(
                        f"[FlowManager] 获取Call类型 {node_config.type} 失败: {e}")
                    controlled_output = False

                if controlled_output:
                    parameters = node_config.params  # 直接使用保存的完整params
                else:
                    # 其他节点：使用原有逻辑
                    input_parameters = node_config.params.get(
                        "input_parameters")
                    _, output_parameters = await NodeManager.get_node_params(node_config.node)

                    # 对于循环节点，输出参数已经是扁平化格式，不需要再次处理
                    if hasattr(node_config, 'type') and node_config.type == "Loop":
                        processed_output_parameters = output_parameters
                    else:
                        processed_output_parameters = Slot(
                            output_parameters).extract_type_desc_from_schema()
                        # 如果输出参数是对象类型，直接使用 items 字段，去除顶层包装
                        # 这样 {type: 'object', items: {reply: {...}}} 会变成 {reply: {...}}
                        if isinstance(processed_output_parameters, dict) and processed_output_parameters.get("type") == "object" and "items" in processed_output_parameters:
                            processed_output_parameters = processed_output_parameters["items"]

                    parameters = {
                        "input_parameters": input_parameters,
                        "output_parameters": processed_output_parameters,
                    }

                # 从Step中读取serviceId和pluginType
                service_id = getattr(node_config, 'service_id', "")
                plugin_type = getattr(node_config, 'plugin_type', None)

                node_item = NodeItem(
                    stepId=node_id,
                    serviceId=service_id,
                    nodeId=node_config.node,
                    name=node_config.name,
                    description=node_config.description,
                    enable=True,
                    editable=True,
                    callId=node_config.type,
                    parameters=parameters,
                    position=PositionItem(
                        x=node_config.pos.x, y=node_config.pos.y),
                    pluginType=plugin_type,
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

            # 处理notes
            for note_config in flow_config.notes:
                flow_item.notes.append(
                    NoteItem(
                        noteId=note_config.note_id,
                        text=note_config.text,
                        position=note_config.position,
                        width=note_config.width,
                        height=note_config.height,
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
        edge_list_1 = [(edge.edge_from, edge.edge_to)
                       for edge in flow_config_1.edges]
        edge_list_2 = [(edge.edge_from, edge.edge_to)
                       for edge in flow_config_2.edges]

        return sorted(edge_list_1) == sorted(edge_list_2)

    @staticmethod
    async def put_flow_by_app_and_flow_id(
        app_id: str,
        flow_id: str,
        flow_item: FlowItem,
        user_sub: str = "",
    ) -> FlowItem | None:
        """
        存储/更新flow的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 流的id
        :param flow_item: 流的item
        :return: 流的id
        """
        import time
        st = time.time()
        try:
            app_collection = MongoDB.get_collection("app")
            app_record = await app_collection.find_one({"_id": app_id})
            if app_record is None:
                logger.error("[FlowManager] 应用 %s 不存在", app_id)
                return None
        except Exception:
            logger.exception("[FlowManager] 获取流失败")
            return None
        en = time.time()
        logger.info(f"[FlowManager] 获取应用时间: {en-st}s")
        try:
            flow_config = Flow(
                name=flow_item.name,
                description=flow_item.description,
                steps={},
                edges=[],
                notes=[],
                focus_point=flow_item.focus_point,
                connectivity=flow_item.connectivity,
                debug=flow_item.debug,
            )
            st = time.time()
            # 获取旧的flow配置以便比较节点变化
            flow_loader = FlowLoader()
            old_flow_config = await flow_loader.load(app_id, flow_id)
            en = time.time()
            logger.info(f"[FlowManager] 加载旧流配置时间: {en-st}s")
            # 收集新配置中的所有步骤ID
            new_step_ids = set()
            st = time.time()
            for node_item in flow_item.nodes:
                params = node_item.parameters
                new_step_ids.add(node_item.step_id)

                # 处理节点变量模板（支持多种节点类型）
                if user_sub:
                    await FlowManager._process_node_variable_templates(
                        node_item, flow_id, user_sub
                    )

                flow_config.steps[node_item.step_id] = Step(
                    type=node_item.call_id,
                    node=node_item.node_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=node_item.position,
                    params=params,
                    service_id=node_item.service_id,
                    plugin_type=node_item.plugin_type,
                )
            en = time.time()
            logger.info(f"[FlowManager] 处理节点时间: {en-st}s")
            st = time.time()
            # 检查是否有节点被删除，如果有则清理相关变量
            if old_flow_config and user_sub:
                old_step_ids = set(old_flow_config.steps.keys())
                deleted_step_ids = old_step_ids - new_step_ids

                if deleted_step_ids:
                    logger.info(f"[FlowManager] 检测到删除的节点: {deleted_step_ids}")
                    # 清理删除节点的相关变量
                    await FlowManager._cleanup_deleted_node_variables(
                        deleted_step_ids, flow_id, user_sub
                    )
            en = time.time()
            logger.info(f"[FlowManager] 清理删除节点变量时间: {en-st}s")
            st = time.time()
            for edge_item in flow_item.edges:
                try:
                    edge_from = edge_item.source_node
                    if edge_item.branch_id:
                        edge_from = edge_from + "." + edge_item.branch_id

                    # 安全处理EdgeType
                    edge_type = EdgeType.NORMAL
                    if edge_item.type:
                        try:
                            edge_type = EdgeType(edge_item.type)
                        except ValueError:
                            logger.warning(
                                f"[FlowManager] 无效的边类型: {edge_item.type}，使用默认值")
                            edge_type = EdgeType.NORMAL

                    edge_config = Edge(
                        id=edge_item.edge_id,
                        edge_from=edge_from,
                        edge_to=edge_item.target_node,
                        edge_type=edge_type,
                    )
                    flow_config.edges.append(edge_config)
                    logger.info(
                        f"[FlowManager] 添加边: {edge_item.edge_id}, {edge_from} -> {edge_item.target_node}, type: {edge_type}")
                except Exception as e:
                    logger.error(
                        f"[FlowManager] 创建边失败: {edge_item.edge_id}, 错误: {e}")
                    continue
            en = time.time()
            logger.info(f"[FlowManager] 处理边时间: {en-st}s")
            st = time.time()
            # 处理notes
            for note_item in flow_item.notes:
                try:
                    note_config = Note(
                        note_id=note_item.note_id,
                        text=note_item.text,
                        position=note_item.position,
                        width=note_item.width,
                        height=note_item.height,
                    )
                    flow_config.notes.append(note_config)
                    logger.info(f"[FlowManager] 添加备注: {note_item.note_id}")
                except Exception as e:
                    logger.error(
                        f"[FlowManager] 创建备注失败: {note_item.note_id}, 错误: {e}")
                    continue
            en = time.time()
            logger.info(f"[FlowManager] 处理备注时间: {en-st}s")
            logger.info(
                f"[FlowManager] 构建完成，flow_config.edges数量: {len(flow_config.edges)}, flow_config.notes数量: {len(flow_config.notes)}")
            st = time.time()
            if old_flow_config is None:
                error_msg = f"[FlowManager] 流 {flow_id} 不存在；可能为新创建"
                logger.error(error_msg)
            elif old_flow_config.debug:
                flow_config.debug = await FlowManager.is_flow_config_equal(old_flow_config, flow_config)
            else:
                flow_config.debug = False
            en = time.time()
            logger.info(f"[FlowManager] 比较流配置时间: {en-st}s")
            st = time.time()
            await flow_loader.save(app_id, flow_id, flow_config)
            en = time.time()
            logger.info(f"[FlowManager] 保存流配置时间: {en-st}s")
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

            app_collection = MongoDB.get_collection("app")
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

    @staticmethod
    async def _process_node_variable_templates(
        node_item: NodeItem,
        flow_id: str,
        user_sub: str
    ) -> None:
        """处理节点变量模板，将其保存到Flow变量池供后续节点引用

        支持的节点类型和配置：
        - Loop节点：从input_parameters.variables提取
        - 其他节点可以扩展支持

        Args:
            node_item: 节点项
            flow_id: 工作流ID
            user_sub: 用户ID
        """
        # 根据节点类型确定变量提取策略
        variables_config = await FlowManager._extract_node_variables_config(node_item)
        if not variables_config:
            return

        # 批量保存变量模板
        await FlowManager._save_node_variables_batch(
            variables_config, node_item.step_id, flow_id, user_sub
        )

    @staticmethod
    async def _extract_node_variables_config(node_item: NodeItem) -> dict[str, any] | None:
        """从节点中提取变量配置

        Args:
            node_item: 节点项

        Returns:
            dict[str, any] | None: 变量配置字典，格式为{变量名: 变量配置}
        """
        try:
            if not node_item.parameters or not isinstance(node_item.parameters, dict):
                return None

            # 根据节点类型提取变量
            if node_item.call_id == "Loop":
                # Loop节点：从input_parameters.variables提取
                input_parameters = node_item.parameters.get(
                    "input_parameters", {})
                if isinstance(input_parameters, dict):
                    variables = input_parameters.get("variables", {})
                    if isinstance(variables, dict) and variables:
                        return variables

            # 可以在这里添加其他节点类型的变量提取逻辑
            # elif node_item.call_id == "OtherNodeType":
            #     return FlowManager._extract_other_node_variables(node_item)

            return None

        except Exception as e:
            logger.error(
                f"[FlowManager] 提取节点 {node_item.step_id} 的变量配置失败: {e}")
            return None

    @staticmethod
    async def _save_node_variables_batch(
        variables_config: dict[str, any],
        step_id: str,
        flow_id: str,
        user_sub: str
    ) -> None:
        """批量保存节点变量模板

        Args:
            variables_config: 变量配置字典
            step_id: 节点步骤ID
            flow_id: 工作流ID
            user_sub: 用户ID
        """
        try:

            saved_count = 0
            failed_count = 0

            for var_name, var_value in variables_config.items():
                try:
                    # 构造变量名：step_id.变量名
                    full_var_name = f"{step_id}.{var_name}"

                    # 解析变量配置
                    var_type, actual_value, description = FlowManager._parse_variable_config(
                        var_value, var_name, step_id
                    )

                    # 保存变量模板
                    success = await FlowManager._save_variable_template(
                        var_name=full_var_name,
                        value=actual_value,
                        var_type=var_type,
                        description=description,
                        user_sub=user_sub,
                        flow_id=flow_id
                    )

                    if success:
                        saved_count += 1
                        logger.debug(
                            f"[FlowManager] 已保存节点变量: conversation.{full_var_name} = {actual_value}")
                    else:
                        failed_count += 1
                        logger.warning(
                            f"[FlowManager] 保存节点变量失败: {full_var_name}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"[FlowManager] 处理节点变量 {var_name} 失败: {e}")

            if saved_count > 0:
                logger.info(
                    f"[FlowManager] 节点 {step_id} 成功保存了 {saved_count} 个变量模板")
            if failed_count > 0:
                logger.warning(
                    f"[FlowManager] 节点 {step_id} 有 {failed_count} 个变量保存失败")

        except Exception as e:
            logger.error(f"[FlowManager] 批量保存节点 {step_id} 的变量失败: {e}")

    @staticmethod
    def _parse_variable_config(var_value: any, var_name: str, step_id: str) -> tuple[str, any, str]:
        """解析变量配置，返回类型、值和描述

        Args:
            var_value: 变量值配置
            var_name: 变量名
            step_id: 节点步骤ID

        Returns:
            tuple[str, any, str]: (变量类型, 实际值, 描述)
        """
        if isinstance(var_value, dict) and "type" in var_value:
            # 复杂格式：{type: "string", value: "默认值", description: "描述"}
            var_type = var_value.get("type", "string")
            actual_value = var_value.get("value", "")
            description = var_value.get(
                "description", f"节点 {step_id} 的变量 {var_name}")
        else:
            # 简单格式：直接值，根据Python类型推断
            actual_value = var_value
            description = f"节点 {step_id} 的变量 {var_name}"

            # 类型推断
            if isinstance(var_value, bool):
                var_type = "boolean"
            elif isinstance(var_value, (int, float)):
                var_type = "number"
            elif isinstance(var_value, (list, tuple)):
                var_type = "array"
            elif isinstance(var_value, dict):
                var_type = "object"
            else:
                var_type = "string"

        return var_type, actual_value, description

    @staticmethod
    async def _save_variable_template(
        var_name: str,
        value: Any,
        var_type: str,
        description: str,
        user_sub: str,
        flow_id: str
    ) -> bool:
        """保存节点变量模板到Flow级别的对话变量模板池

        Args:
            var_name: 变量名（格式：step_id.变量名）
            value: 变量值
            var_type: 变量类型
            description: 变量描述
            user_sub: 用户ID
            flow_id: 流程ID

        Returns:
            bool: 是否保存成功
        """
        try:
            # 导入必要的模块
            from apps.scheduler.variable.pool_manager import get_pool_manager
            from apps.scheduler.variable.type import VariableType

            # 获取flow级别的变量池
            pool_manager = await get_pool_manager()
            flow_pool = await pool_manager.get_flow_pool(flow_id)

            if not flow_pool:
                logger.warning(f"[FlowManager] 无法获取Flow变量池: {flow_id}")
                return False

            # 转换变量类型
            try:
                var_type_enum = VariableType(var_type)
            except ValueError:
                var_type_enum = VariableType.STRING
                logger.warning(
                    f"[FlowManager] 未知的变量类型 {var_type}，使用默认类型 string")

            # 尝试更新对话变量模板，如果不存在则创建
            try:
                # 检查是否已存在对话变量模板
                existing_template = await flow_pool.get_conversation_template(var_name)
                if existing_template:
                    # 更新现有模板 - 使用通用的update_variable方法
                    await flow_pool.update_variable(var_name, value=value, description=description)
                    logger.debug(
                        f"[FlowManager] 节点变量模板已更新: {var_name} = {value}")
                else:
                    # 创建新的对话变量模板
                    await flow_pool.add_conversation_template(
                        name=var_name,
                        var_type=var_type_enum,
                        default_value=value,  # 注意参数名是default_value，不是value
                        description=description,
                        created_by=user_sub or "system"
                    )
                    logger.debug(
                        f"[FlowManager] 节点变量模板已创建: {var_name} = {value}")
                return True
            except Exception as e:
                logger.error(f"[FlowManager] 处理节点变量模板失败: {var_name}, 错误: {e}")
                return False

        except Exception as e:
            logger.error(f"[FlowManager] 保存节点变量模板失败: {var_name}, 错误: {e}")
            return False

    @staticmethod
    async def put_subflow_by_app_flow_and_subflow_id(
        app_id: str,
        flow_id: str,
        sub_flow_id: str,
        flow_item: FlowItem,
    ) -> FlowItem | None:
        """
        存储/更新子工作流的数据库数据和配置文件

        :param app_id: 应用的id
        :param flow_id: 父工作流的id
        :param sub_flow_id: 子工作流的id
        :param flow_item: 子工作流的item
        :return: 子工作流的item
        """
        try:
            app_collection = MongoDB.get_collection("app")
            app_record = await app_collection.find_one({"_id": app_id})
            if app_record is None:
                logger.error("[FlowManager] 应用 %s 不存在", app_id)
                return None
        except Exception:
            logger.exception("[FlowManager] 获取应用失败")
            return None

        try:
            # 构建子工作流配置
            flow_config = Flow(
                name=flow_item.name,
                description=flow_item.description,
                steps={},
                edges=[],
                notes=[],
                focus_point=flow_item.focus_point,
                connectivity=flow_item.connectivity,
                debug=flow_item.debug,
            )

            for node_item in flow_item.nodes:
                params = node_item.parameters
                flow_config.steps[node_item.step_id] = Step(
                    type=node_item.call_id,
                    node=node_item.node_id,
                    name=node_item.name,
                    description=node_item.description,
                    pos=node_item.position,
                    params=params,
                    service_id=node_item.service_id,
                    plugin_type=node_item.plugin_type,
                )

            for edge_item in flow_item.edges:
                edge_from = edge_item.source_node
                if edge_item.branch_id:
                    edge_from = edge_from + "." + edge_item.branch_id

                edge_config = Edge(
                    id=edge_item.edge_id,
                    edge_from=edge_from,
                    edge_to=edge_item.target_node,
                    edge_type=EdgeType.NORMAL,  # 子工作流默认使用普通边
                )
                flow_config.edges.append(edge_config)

            # 处理notes
            for note_item in flow_item.notes:
                try:
                    note_config = Note(
                        note_id=note_item.note_id,
                        text=note_item.text,
                        position=note_item.position,
                        width=note_item.width,
                        height=note_item.height,
                    )
                    flow_config.notes.append(note_config)
                    logger.info(f"[FlowManager] 子工作流添加备注: {note_item.note_id}")
                except Exception as e:
                    logger.error(
                        f"[FlowManager] 子工作流创建备注失败: {note_item.note_id}, 错误: {e}")
                    continue

            # 使用子工作流专用的保存路径
            flow_loader = FlowLoader()
            await flow_loader.save_subflow(app_id, flow_id, sub_flow_id, flow_config)

            return flow_item

        except Exception:
            logger.exception("[FlowManager] 保存子工作流失败")
            return None

    @staticmethod
    async def get_subflow_by_app_flow_and_subflow_id(
        app_id: str,
        flow_id: str,
        sub_flow_id: str,
    ) -> FlowItem | None:
        """
        根据应用id、父工作流id和子工作流id获取子工作流

        :param app_id: 应用的id
        :param flow_id: 父工作流的id  
        :param sub_flow_id: 子工作流的id
        :return: 子工作流的FlowItem
        """
        try:
            flow_loader = FlowLoader()
            flow_config = await flow_loader.load_subflow(app_id, flow_id, sub_flow_id)

            if flow_config is None:
                return None

            # 转换为FlowItem格式
            focus_point = flow_config.focus_point or PositionItem(x=0, y=0)
            flow_item = FlowItem(
                flowId=sub_flow_id,
                name=flow_config.name,
                description=flow_config.description,
                enable=True,
                editable=True,
                nodes=[],
                edges=[],
                notes=[],
                focusPoint=focus_point,
                connectivity=flow_config.connectivity,
                debug=flow_config.debug,
            )

            for node_id, node_config in flow_config.steps.items():
                # 参数处理逻辑与主工作流保持一致
                if node_config.type == "Code" or node_config.type == "DirectReply" or node_config.type == "Choice" or node_config.type == "FileExtract":
                    parameters = node_config.params  # 直接使用保存的完整params
                else:
                    # 其他节点：使用原有逻辑
                    input_parameters = node_config.params.get(
                        "input_parameters")
                    if node_config.node not in ("Empty"):
                        try:
                            _, output_parameters = await NodeManager.get_node_params(node_config.node)
                        except Exception:
                            logger.exception("[FlowManager] 获取节点参数失败，使用空参数")
                            output_parameters = {}
                    else:
                        output_parameters = {}

                    # 对于循环节点，输出参数已经是扁平化格式，不需要再次处理
                    if hasattr(node_config, 'type') and node_config.type == "Loop":
                        processed_output_parameters = output_parameters
                    else:
                        processed_output_parameters = Slot(
                            output_parameters).extract_type_desc_from_schema()

                    parameters = {
                        "input_parameters": input_parameters,
                        "output_parameters": processed_output_parameters,
                    }

                # 从Step中读取pluginType
                plugin_type = getattr(node_config, 'plugin_type', None)

                node_item = NodeItem(
                    stepId=node_id,
                    serviceId="",  # 子工作流节点默认serviceId为空
                    nodeId=node_config.node,
                    name=node_config.name,
                    description=node_config.description,
                    enable=True,
                    editable=True,
                    callId=node_config.type,
                    parameters=parameters,
                    position=PositionItem(
                        x=node_config.pos.x, y=node_config.pos.y),
                    pluginType=plugin_type,
                )
                flow_item.nodes.append(node_item)

            for edge_config in flow_config.edges:
                edge_from = edge_config.edge_from
                branch_id = ""
                tmp_list = edge_config.edge_from.split(".")
                if len(tmp_list) == 0 or len(tmp_list) > 2:
                    logger.error("[FlowManager] 子工作流中边的格式错误")
                    continue
                if len(tmp_list) == 2:
                    edge_from = tmp_list[0]
                    branch_id = tmp_list[1]

                edge_item = EdgeItem(
                    edgeId=edge_config.id,
                    sourceNode=edge_from,
                    targetNode=edge_config.edge_to,
                    type=edge_config.edge_type.value if edge_config.edge_type else EdgeType.NORMAL.value,
                    branchId=branch_id,
                )
                flow_item.edges.append(edge_item)

            # 处理notes
            for note_config in flow_config.notes:
                flow_item.notes.append(
                    NoteItem(
                        noteId=note_config.note_id,
                        text=note_config.text,
                        position=note_config.position,
                        width=note_config.width,
                        height=note_config.height,
                    ),
                )

            return flow_item

        except Exception:
            logger.exception("[FlowManager] 获取子工作流失败")
            return None

    @staticmethod
    async def delete_subflow_by_app_flow_and_subflow_id(
        app_id: str,
        flow_id: str,
        sub_flow_id: str,
    ) -> bool:
        """
        删除子工作流

        :param app_id: 应用的id
        :param flow_id: 父工作流的id
        :param sub_flow_id: 子工作流的id
        :return: 是否删除成功
        """
        try:
            flow_loader = FlowLoader()
            return await flow_loader.delete_subflow(app_id, flow_id, sub_flow_id)
        except Exception:
            logger.exception("[FlowManager] 删除子工作流失败")
            return False

    @staticmethod
    async def _cleanup_deleted_node_variables(
        deleted_step_ids: set[str],
        flow_id: str,
        user_sub: str
    ) -> None:
        """清理被删除节点的相关变量

        Args:
            deleted_step_ids: 被删除的步骤ID集合
            flow_id: 工作流ID
            user_sub: 用户ID
        """
        try:
            from apps.scheduler.variable.pool_manager import get_pool_manager

            # 获取flow级别的变量池
            pool_manager = await get_pool_manager()
            flow_pool = await pool_manager.get_flow_pool(flow_id)

            if not flow_pool:
                logger.warning(f"[FlowManager] 无法获取Flow变量池: {flow_id}")
                return

            # 获取所有对话变量模板
            conversation_variables = await flow_pool.list_conversation_templates()

            if not conversation_variables:
                logger.info(f"[FlowManager] 没有找到对话变量需要清理")
                return

            cleaned_count = 0

            for variable in conversation_variables:
                try:
                    # 检查变量名是否以被删除的步骤ID开头
                    for deleted_step_id in deleted_step_ids:
                        if variable.name.startswith(f"{deleted_step_id}."):
                            # 删除该变量
                            await flow_pool.delete_variable(variable.name)
                            cleaned_count += 1
                            logger.info(
                                f"[FlowManager] 已清理删除节点的变量: {variable.name}")
                            break
                except Exception as e:
                    logger.error(f"[FlowManager] 清理变量 {variable.name} 失败: {e}")

            if cleaned_count > 0:
                logger.info(f"[FlowManager] 总共清理了 {cleaned_count} 个被删除节点的变量")
            else:
                logger.info(f"[FlowManager] 没有找到需要清理的节点变量")

        except Exception as e:
            logger.error(f"[FlowManager] 清理删除节点变量失败: {e}")
