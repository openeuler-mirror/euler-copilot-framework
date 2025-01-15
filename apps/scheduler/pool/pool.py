"""数据池

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import hashlib
import hmac
import json
import pickle
from threading import Lock
from typing import Any, ClassVar, Optional

import chromadb
from langchain_community.agent_toolkits.openapi.spec import ReducedOpenAPISpec
from rank_bm25 import BM25Okapi
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from apps.common.config import config
from apps.common.singleton import Singleton
from apps.constants import LOGGER
from apps.entities.flow import Flow
from apps.entities.plugin import PluginData
from apps.scheduler.pool.entities import Base, CallItem, FlowItem, PluginItem
from apps.scheduler.vector import DocumentWrapper, VectorDB


class Pool(metaclass=Singleton):
    """数据池"""

    write_lock: Lock = Lock()
    relation_db: Engine
    flow_collection: chromadb.Collection
    plugin_collection: chromadb.Collection

    flow_pool: ClassVar[dict[str, Any]] = {}
    call_pool: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        """初始化内存中的SQLite数据库和内存中的ChromaDB"""
        with self.write_lock:
            # Init SQLite
            self.relation_db = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(self.relation_db)

            # Init ChromaDB
            self.create_collection()

    @staticmethod
    def serialize_data(origin_data) -> tuple[bytes, str]:  # noqa: ANN001
        """使用Pickle序列化数据

        为保证数据不被篡改，使用HMAC对数据进行签名
        """
        data = pickle.dumps(origin_data)
        hmac_obj = hmac.new(key=bytes.fromhex(config["PICKLE_KEY"]), msg=data, digestmod=hashlib.sha256)
        signature = hmac_obj.hexdigest()
        return data, signature

    @staticmethod
    def deserialize_data(data: bytes, signature: str):  # noqa: ANN205
        """反序列化数据

        使用HMAC对数据进行签名验证
        """
        hmac_obj = hmac.new(key=bytes.fromhex(config["PICKLE_KEY"]), msg=data, digestmod=hashlib.sha256)
        current_signature = hmac_obj.hexdigest()
        if current_signature != signature:
            err = "Pickle data has been modified!"
            raise AssertionError(err)

        return pickle.loads(data)  # noqa: S301

    def create_collection(self) -> None:
        """创建ChromaDB的Collection"""
        flow_collection = VectorDB.get_collection("flow")
        if flow_collection is None:
            err = "Create flow collection failed!"
            raise RuntimeError(err)
        self.flow_collection = flow_collection

        plugin_collection = VectorDB.get_collection("plugin")
        if plugin_collection is None:
            err = "Create plugin collection failed!"
            raise RuntimeError(err)
        self.plugin_collection = plugin_collection

    def add_plugin(self, plugin_id: str, metadata: dict, spec: Optional[ReducedOpenAPISpec] = None) -> None:
        """载入单个Plugin"""
        spec_data, signature = self.serialize_data(spec)

        auth = json.dumps(metadata["auth"]) if "auth" in metadata else "{}"

        plugin = PluginItem(
            id=plugin_id,
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
                LOGGER.error(f"Import plugin failed: {e!s}")

        doc = DocumentWrapper(
            data=metadata["description"],
            id=plugin_id,
        )

        with self.write_lock:
            VectorDB.add_docs(self.plugin_collection, [doc])

    def add_flows(self, plugin: str, flows: list[dict[str, Any]]) -> None:
        """载入单个Flow"""
        docs = []
        flow_rows = []

        # 此处，flow在向量数据库中名字加上了plugin前缀，防止ID冲突
        for item in flows:
            current_row = FlowItem(
                plugin=plugin,
                name=item["id"],
                description=item["description"],
            )
            flow_rows.append(current_row)

            doc = DocumentWrapper(
                id=plugin + "/" + item["id"],
                data=item["description"],
                metadata={
                    "plugin": plugin,
                },
            )
            docs.append(doc)
            with self.write_lock:
                self.flow_pool[plugin + "/" + item["id"]] = item["data"]

        with self.write_lock:
            try:
                with sessionmaker(bind=self.relation_db)() as session:
                    session.add_all(flow_rows)
                    session.commit()
            except Exception as e:
                LOGGER.error(f"Import flow failed: {e!s}")
            VectorDB.add_docs(self.flow_collection, docs)

    def add_calls(self, plugin: Optional[str], calls: list[Any]) -> None:
        """载入单个Call"""
        call_metadata = []

        for item in calls:
            current_metadata = CallItem(
                plugin=plugin,
                name=str(item.name),
                description=str(item.description),
            )
            call_metadata.append(current_metadata)

            with self.write_lock:
                call_prefix = ""
                if plugin is not None:
                    call_prefix += plugin + "/"
                self.call_pool[call_prefix + str(item.name)] = item

        with self.write_lock, sessionmaker(bind=self.relation_db)() as session:
            try:
                session.add_all(call_metadata)
                session.commit()
            except Exception as e:
                LOGGER.error(f"Import plugin {plugin} call failed: {e!s}")

    def clean_db(self) -> None:
        """清空SQLite和ChromaDB"""
        try:
            with self.write_lock:
                Base.metadata.drop_all(bind=self.relation_db)
                Base.metadata.create_all(bind=self.relation_db)

                VectorDB.delete_collection("flow")
                VectorDB.delete_collection("plugin")
                self.create_collection()

                Pool.flow_pool = {}
                Pool.call_pool = {}
        except Exception as e:
            LOGGER.error(f"Clean DB failed: {e!s}")


    def get_plugin_list(self) -> list[PluginData]:
        """从数据库中获取所有插件信息"""
        try:
            with sessionmaker(bind=self.relation_db)() as session:
                result = session.query(PluginItem).all()
        except Exception as e:
            LOGGER.error(f"Get Plugin from DB failed: {e!s}")
            return []

        plugin_list: list[PluginData] = [PluginData(
                id=str(item.id),
                name=str(item.show_name),
                description=str(item.description),
                auth=json.loads(str(item.auth)),
            )
            for item in result
        ]

        return plugin_list

    def get_flow(self, name: str, plugin: str) -> tuple[Optional[FlowItem], Optional[Flow]]:
        """查找Flow名对应的元数据和Step"""
        try:
            with sessionmaker(bind=self.relation_db)() as session:
                result = session.query(FlowItem).filter_by(name=name, plugin=plugin).first()
        except Exception as e:
            LOGGER.error(f"Get Flow from DB failed: {e!s}")
            return None, None

        return result, self.flow_pool.get(plugin + "/" + name, None)


    def get_plugin(self, name: str) -> Optional[PluginItem]:
        """查找Plugin名对应的元数据"""
        try:
            with sessionmaker(bind=self.relation_db)() as session:
                result = session.query(PluginItem).filter_by(id=name).first()
        except Exception as e:
            LOGGER.error(f"Get Plugin from DB failed: {e!s}")
            return None

        return result

    def get_k_plugins(self, question: str, top_k: int = 5) -> list[PluginItem]:
        """查找k个最符合条件的Plugin，返回数据"""
        result = self.plugin_collection.query(
            query_texts=[question],
            n_results=top_k,
        )

        ids = result.get("ids", None)
        if ids is None:
            LOGGER.error(f"Vector search failed: {result}")
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
                    LOGGER.error(f"Get data from VectorDB failed: {e!s}")

        return result_list

    def get_k_flows(self, question: str, plugin_list: list[str], top_k: int = 5) -> list[FlowItem]:
        """查找k个最符合条件的Flow，返回数据"""
        result = self.flow_collection.query(
            query_texts=[question],
            n_results=top_k * 4,
            where=Pool._construct_vector_query(plugin_list),
        )

        ids = result.get("ids", None)
        docs = result.get("documents", None)
        if ids is None or docs is None:
            LOGGER.error(f"Vector search failed: {result}")
            return []

        # 使用bm25s进行重排，此处list有序；考虑到文字可能很短，因此直接用字符作为token
        corpus = [list(item) for item in docs[0]]
        question_tokens = list(question)
        retriever = BM25Okapi(corpus)
        corpus_ids = list(range(len(corpus)))
        results = retriever.get_top_n(question_tokens, corpus_ids, top_k)
        retrieved_ids = [ids[0][i] for i in results]

        result_list = []
        with sessionmaker(bind=self.relation_db)() as session:
            for current_id in retrieved_ids:
                plugin_name, flow_name = current_id.split("/")
                try:
                    result_item = session.query(FlowItem).filter_by(name=flow_name, plugin=plugin_name).first()
                    if result_item is None:
                        continue
                    result_list.append(result_item)
                except Exception as e:
                    LOGGER.error(f"Get data from VectorDB failed: {e!s}")

        return result_list

    @staticmethod
    def _construct_vector_query(plugin_list: list[str]) -> dict[str, Any]:
        constraint = {}
        if len(plugin_list) == 0:
            return {}
        if len(plugin_list) == 1:
            constraint["plugin"] = {
                "$eq": plugin_list[0],
            }
        else:
            constraint["$or"] = []
            for plugin in plugin_list:
                constraint["$or"].append({
                    "plugin": {
                        "$eq": plugin,
                    },
                })
        return constraint


    def get_call(self, name: str, plugin: str) -> tuple[Optional[CallItem], Optional[Any]]:
        """从Call Pool里面拿出对应的Call类

        :param name:
        :param plugin:
        :return:
        """
        if plugin:
            try:
                with sessionmaker(bind=self.relation_db)() as session:
                    call_item = session.query(CallItem).filter_by(name=name).filter_by(plugin=plugin).first()
                    if call_item:
                        return call_item, self.call_pool.get(name, None)
            except Exception as e:
                LOGGER.error(f"Get Call from DB failed: {e!s}")
                return None, None

        try:
            with sessionmaker(bind=self.relation_db)() as session:
                call_item = session.query(CallItem).filter_by(name=name).filter_by(plugin=None).first()
                if call_item:
                    return call_item, self.call_pool.get(name, None)
        except Exception as e:
            LOGGER.error(f"Get Call from DB failed: {e!s}")
            return None, None

        return None, None
