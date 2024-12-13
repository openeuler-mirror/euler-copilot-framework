# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import hashlib
from threading import Lock
import pickle
import hmac
import json
from typing import Tuple, Dict, Any, List
import logging

from sqlalchemy import create_engine, Engine, or_
from sqlalchemy.orm import sessionmaker
from langchain_community.agent_toolkits.openapi.spec import ReducedOpenAPISpec
import chromadb

from apps.common.singleton import Singleton
from apps.scheduler.vector import VectorDB, DocumentWrapper
from apps.scheduler.pool.entities import Base
from apps.common.config import config
from apps.scheduler.pool.entities import PluginItem, FlowItem, CallItem
from apps.entities.plugin import PluginData
from apps.entities.plugin import Flow


logger = logging.getLogger('gunicorn.error')


class Pool(metaclass=Singleton):
    write_lock: Lock = Lock()
    relation_db: Engine
    flow_collection: chromadb.Collection
    plugin_collection: chromadb.Collection

    flow_pool: Dict[str, Any] = {}
    call_pool: Dict[str, Any] = {}

    def __init__(self):
        with self.write_lock:
            # Init SQLite
            self.relation_db = create_engine('sqlite:///:memory:')
            Base.metadata.create_all(self.relation_db)

            # Init ChromaDB
            self.create_collection()

    @staticmethod
    def serialize_data(origin_data) -> Tuple[bytes, str]:
        data = pickle.dumps(origin_data)
        hmac_obj = hmac.new(key=bytes.fromhex(config["PICKLE_KEY"]), msg=data, digestmod=hashlib.sha256)
        signature = hmac_obj.hexdigest()
        return data, signature

    @staticmethod
    def deserialize_data(data: bytes, signature: str):
        hmac_obj = hmac.new(key=bytes.fromhex(config["PICKLE_KEY"]), msg=data, digestmod=hashlib.sha256)
        current_signature = hmac_obj.hexdigest()
        if current_signature != signature:
            raise AssertionError("Pickle data has been modified!")

        return pickle.loads(data)

    def create_collection(self):
        self.flow_collection = VectorDB.get_collection("flow")
        self.plugin_collection = VectorDB.get_collection("plugin")

    def add_plugin(self, name: str, metadata: dict, spec: ReducedOpenAPISpec | None):
        spec_data, signature = self.serialize_data(spec)

        if "auth" in metadata:
            auth = json.dumps(metadata["auth"])
        else:
            auth = "{}"

        plugin = PluginItem(
            name=name,
            show_name=metadata["name"],
            description=metadata["description"],
            auth=auth,
            spec=spec_data,
            signature=signature,
        )
        with self.write_lock:
            try:
                with sessionmaker(bind=self.relation_db)() as session:
                    session.add(plugin)
                    session.commit()
            except Exception as e:
                logger.error(f"Import plugin failed: {str(e)}")

        doc = DocumentWrapper(
            data=metadata["description"],
            id=name
        )

        with self.write_lock:
            VectorDB.add_docs(self.plugin_collection, [doc])

    def add_flows(self, plugin: str, flows: List[Dict[str, Any]]):
        docs = []
        flow_rows = []

        # 此处，flow在向量数据库中名字加上了plugin前缀，防止ID冲突
        for item in flows:
            current_row = FlowItem(
                plugin=plugin,
                name=item["name"],
                description=item["description"]
            )
            flow_rows.append(current_row)

            doc = DocumentWrapper(
                id=plugin + "." + item["name"],
                data=item["description"],
                metadata={
                    "plugin": plugin
                }
            )
            docs.append(doc)
            with self.write_lock:
                self.flow_pool[plugin + "." + item["name"]] = item["data"]

        with self.write_lock:
            try:
                with sessionmaker(bind=self.relation_db)() as session:
                    session.add_all(flow_rows)
                    session.commit()
            except Exception as e:
                logger.error(f"Import flow failed: {str(e)}")
            VectorDB.add_docs(self.flow_collection, docs)

    def add_calls(self, plugin: str | None, calls: List[Any]):
        call_metadata = []

        for item in calls:
            current_metadata = CallItem(
                plugin=plugin,
                name=item.name,
                description=item.description
            )
            call_metadata.append(current_metadata)

            with self.write_lock:
                call_prefix = ""
                if plugin is not None:
                    call_prefix += plugin + "."
                self.call_pool[call_prefix + item.name] = item

        with self.write_lock:
            with sessionmaker(bind=self.relation_db)() as session:
                try:
                    session.add_all(call_metadata)
                    session.commit()
                except Exception as e:
                    logger.error(f"Import plugin {plugin} call failed: {str(e)}")

    def clean_db(self):
        try:
            with self.write_lock:
                Base.metadata.drop_all(bind=self.relation_db)
                Base.metadata.create_all(bind=self.relation_db)

                VectorDB.delete_collection("flow")
                VectorDB.delete_collection("plugin")
                self.create_collection()

                self.flow_pool = {}
                self.call_pool = {}
        except Exception as e:
            logger.error(f"Clean DB failed: {str(e)}")


    def get_plugin_list(self) -> List[PluginData]:
        plugin_list: List[PluginData] = []
        try:
            with sessionmaker(bind=self.relation_db)() as session:
                result = session.query(PluginItem).all()
        except Exception as e:
            logger.error(f"Get Plugin from DB failed: {str(e)}")
            return []

        for item in result:
            plugin_list.append(PluginData(
                id=item.name,
                plugin_name=item.show_name,
                plugin_description=item.description,
                plugin_auth=json.loads(item.auth)
            ))

        return plugin_list

    def get_flow(self, name: str, plugin_name: str) -> Tuple[FlowItem | None, Flow | None]:
        # 查找Flow名对应的 信息和Step
        if "." in name:
            plugin, flow = name.split(".")
        else:
            plugin, flow = plugin_name, name

        try:
            with sessionmaker(bind=self.relation_db)() as session:
                result = session.query(FlowItem).filter_by(name=flow, plugin=plugin).first()
        except Exception as e:
            logger.error(f"Get Flow from DB failed: {str(e)}")
            return None, None

        return result, self.flow_pool.get(plugin + "." + flow, None)


    def get_plugin(self, name: str) -> PluginItem | None:
        # 查找Plugin名对应的 信息
        try:
            with sessionmaker(bind=self.relation_db)() as session:
                result = session.query(PluginItem).filter_by(name=name).first()
        except Exception as e:
            logger.error(f"Get Plugin from DB failed: {str(e)}")
            return None

        return result

    def get_k_plugins(self, question: str, top_k: int = 3):
        result = self.plugin_collection.query(
            query_texts=[question],
            n_results=top_k
        )

        ids = result.get("ids", None)
        if ids is None:
            logger.error(f"Vector search failed: {result}")
            return []

        result_list = []
        with sessionmaker(bind=self.relation_db)() as session:
            for current_id in ids[0]:
                try:
                    result_item = session.query(PluginItem).filter_by(name=current_id).first()
                    if result_item is None:
                        continue
                    result_list.append(result_item)
                except Exception as e:
                    logger.error(f"Get data from VectorDB failed: {str(e)}")

        return result_list

    def get_k_flows(self, question: str, plugin_list: List[str] | None = None, top_k: int = 3) -> List:
        result = self.flow_collection.query(
            query_texts=[question],
            n_results=top_k,
            where=Pool._construct_vector_query(plugin_list)
        )

        ids = result.get("ids", None)
        if ids is None:
            logger.error(f"Vector search failed: {result}")
            return []

        result_list = []
        with sessionmaker(bind=self.relation_db)() as session:
            for current_id in ids[0]:
                plugin_name, flow_name = current_id.split(".")
                try:
                    result_item = session.query(FlowItem).filter_by(name=flow_name, plugin=plugin_name).first()
                    if result_item is None:
                        continue
                    result_list.append(result_item)
                except Exception as e:
                    logger.error(f"Get data from VectorDB failed: {str(e)}")

        return result_list

    @staticmethod
    def _construct_vector_query(plugin_list: List[str]) -> Dict[str, Any]:
        constraint = {}
        if len(plugin_list) == 0:
            return {}
        elif len(plugin_list) == 1:
            constraint["plugin"] = {
                "$eq": plugin_list[0]
            }
        else:
            constraint["$or"] = []
            for plugin in plugin_list:
                constraint["$or"].append({
                    "plugin": {
                        "$eq": plugin
                    }
                })
        return constraint


    def get_call(self, name: str, plugin: str) -> Tuple[CallItem | None, Any]:
        if "." not in name:
            call_name = name
            call_plugin = plugin
        else:
            call_name, call_plugin = name.split(".", 1)

        try:
            with sessionmaker(bind=self.relation_db)() as session:
                call_item = session.query(CallItem).filter_by(name=call_name).filter(or_(CallItem.plugin == call_plugin, CallItem.plugin == None)).first()
        except Exception as e:
            logger.error(f"Get Call from DB failed: {str(e)}")
            return None, None

        return call_item, self.call_pool.get(name, None)
