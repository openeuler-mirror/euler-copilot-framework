"""Call 加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import importlib
import sys
from pathlib import Path

from pydantic import BaseModel

import apps.scheduler.call as system_call
from apps.common.config import config
from apps.constants import CALL_DIR, LOGGER
from apps.entities.enum_var import CallType
from apps.entities.pool import (
    CallPool,
    NodePool,
)
from apps.entities.vector import NodePoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL
from apps.scheduler.pool.util import get_short_hash


class CallLoader:
    """Call 加载器"""

    @staticmethod
    def _check_class(user_cls) -> bool:  # noqa: ANN001
        """检查用户类是否符合Call标准要求"""
        flag = True

        if not hasattr(user_cls, "name") or not isinstance(user_cls.name, str):
            flag = False
        if not hasattr(user_cls, "description") or not isinstance(user_cls.description, str):
            flag = False
        if not hasattr(user_cls, "params") or not issubclass(user_cls.params, BaseModel):
            flag = False
        if not hasattr(user_cls, "init") or not callable(user_cls.init):
            flag = False
        if not hasattr(user_cls, "call") or not callable(user_cls.call):
            flag = False

        if not flag:
            LOGGER.info(msg=f"类{user_cls.__name__}不符合Call标准要求。")

        return flag

    @classmethod
    async def _load_system_call(cls) -> tuple[list[CallPool], list[NodePool]]:
        """加载系统Call"""
        call_metadata = []
        node_metadata = []

        for call_id in system_call.__all__:
            call_cls = getattr(system_call, call_id)
            if not cls._check_class(call_cls):
                err = f"类{call_cls.__name__}不符合Call标准要求。"
                LOGGER.info(msg=err)
                continue

            call_metadata.append(
                CallPool(
                    _id=call_id,
                    type=CallType.SYSTEM,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=call_id,
                ),
            )

            node_metadata.append(
                NodePool(
                    _id=call_id,
                    call_id=call_id,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=call_id,
                ),
            )

        return call_metadata, node_metadata

    @classmethod
    async def _load_single_call_dir(cls, call_name: str) -> tuple[list[CallPool], list[NodePool]]:
        """加载单个Call package"""
        call_metadata = []
        node_metadata = []

        call_dir = Path(config["SERVICE_DIR"]) / CALL_DIR / call_name
        if not (call_dir / "__init__.py").exists():
            LOGGER.info(msg=f"模块{call_dir}不存在__init__.py文件，尝试自动创建。")
            try:
                (Path(call_dir) / "__init__.py").touch()
            except Exception as e:
                err = f"自动创建模块文件{call_dir}/__init__.py失败：{e}。"
                raise RuntimeError(err) from e

        # 载入子包
        try:
            call_package = importlib.import_module("call." + call_name)
        except Exception as e:
            err = f"载入模块call.{call_name}失败：{e}。"
            raise RuntimeError(err) from e

        # 已载入包，处理包中每个工具
        if not hasattr(call_package, "__all__"):
            err = f"包call.{call_name}不符合模块要求，无法处理。"
            LOGGER.info(msg=err)
            raise ValueError(err)

        for call_id in call_package.__all__:
            try:
                call_cls = getattr(call_package, call_id)
            except Exception as e:
                err = f"载入工具{call_name}.{call_id}失败：{e}；跳过载入。"
                LOGGER.info(msg=err)
                continue

            if not cls._check_class(call_cls):
                err = f"工具{call_name}.{call_id}不符合标准要求；跳过载入。"
                LOGGER.info(msg=err)
                continue

            cls_path = f"{call_package.service}::call.{call_name}.{call_id}"
            cls_hash = get_short_hash(cls_path.encode())
            call_metadata.append(
                CallPool(
                    _id=cls_hash,
                    type=CallType.PYTHON,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=cls_path,
                ),
            )
            node_metadata.append(
                NodePool(
                    _id=cls_hash,
                    call_id=cls_hash,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=cls_path,
                ),
            )

        return call_metadata, node_metadata

    @classmethod
    async def _load_all_user_call(cls) -> tuple[list[CallPool], list[NodePool]]:
        """加载Python Call"""
        call_dir = Path(config["SERVICE_DIR"]) / CALL_DIR
        call_metadata = []
        node_metadata = []

        # 载入父包
        try:
            sys.path.insert(0, str(call_dir))
            if not (call_dir / "__init__.py").exists():
                LOGGER.info(msg=f"父模块{call_dir}不存在__init__.py文件，尝试自动创建。")
                (Path(call_dir) / "__init__.py").touch()
            importlib.import_module("call")
        except Exception as e:
            err = f'父模块"call"创建失败：{e}；无法载入。'
            raise RuntimeError(err) from e

        # 处理每一个子包
        for call_file in Path(call_dir).rglob("*"):
            if not call_file.is_dir():
                continue
            # 载入包
            try:
                call_metadata, node_metadata = await CallLoader._load_single_call_dir(call_file.name)
                call_metadata.extend(call_metadata)
                node_metadata.extend(node_metadata)

            except Exception as e:
                err = f"载入模块{call_file}失败：{e}，跳过载入。"
                LOGGER.info(msg=err)
                continue

        return call_metadata, node_metadata


    # TODO: 动态卸载


    # 更新数据库
    @staticmethod
    async def _update_db(call_metadata: list[CallPool], node_metadata: list[NodePool]) -> None:
        """更新数据库；call和node下标一致"""
        # 更新MongoDB
        call_collection = MongoDB.get_collection("call")
        node_collection = MongoDB.get_collection("node")
        try:
            for call, node in zip(call_metadata, node_metadata):
                await call_collection.update_one({"_id": call.id}, {"$set": call.model_dump(exclude_none=True, by_alias=True)}, upsert=True)
                await node_collection.update_one({"_id": node.id}, {"$set": node.model_dump(exclude_none=True, by_alias=True)}, upsert=True)
        except Exception as e:
            err = f"更新MongoDB失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        # 进行向量化，更新PostgreSQL
        node_descriptions = []
        for node in node_metadata:
            node_descriptions += [node.description]

        session = await PostgreSQL.get_session()
        node_vecs = await PostgreSQL.get_embedding(node_descriptions)
        for i, data in enumerate(node_vecs):
            node_vec = NodePoolVector(
                _id=node_metadata[i].id,
                embedding=data,
            )
            session.add(node_vec)
        await session.commit()


    @staticmethod
    async def init() -> None:
        """初始化Call信息"""
        # 清空collection
        call_collection = MongoDB.get_collection("call")
        node_collection = MongoDB.get_collection("node")
        try:
            await call_collection.delete_many({})
            await node_collection.delete_many({})
        except Exception as e:
            LOGGER.error(msg=f"Call和Node的collection清空失败：{e}")

        # 载入所有已知的Call信息
        try:
            sys_call_metadata, sys_node_metadata = await CallLoader._load_system_call()
        except Exception as e:
            err = f"载入系统Call信息失败：{e}；停止运行。"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        user_call_metadata, user_node_metadata = await CallLoader._load_all_user_call()

        # 合并Call元数据
        call_metadata = sys_call_metadata + user_call_metadata
        node_metadata = sys_node_metadata + user_node_metadata

        # 更新数据库
        await CallLoader._update_db(call_metadata, node_metadata)


    @staticmethod
    async def load_one(call_name: str) -> None:
        """加载单个Call"""
        try:
            call_metadata, node_metadata = await CallLoader._load_single_call_dir(call_name)
        except Exception as e:
            err = f"载入Call信息失败：{e}。"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        # 有数据时更新数据库
        if call_metadata:
            await CallLoader._update_db(call_metadata, node_metadata)


    @staticmethod
    async def get() -> list[CallPool]:
        """获取当前已知的所有Python Call元数据"""
        call_collection = MongoDB.get_collection("call")
        result: list[CallPool] = []
        try:
            cursor = call_collection.find({})
            async for item in cursor:
                result.extend([CallPool.model_validate(item)])
        except Exception as e:
            LOGGER.error(msg=f"获取Call元数据失败：{e}")

        return result
