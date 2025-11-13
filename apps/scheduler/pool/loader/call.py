# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Call 加载器"""

import asyncio
import importlib
import logging
import sys
from hashlib import shake_128
from pathlib import Path

import apps.scheduler.call as system_call
from apps.common.config import Config
from apps.common.singleton import SingletonMeta
from apps.schemas.enum_var import CallType
from apps.schemas.pool import CallPool, NodePool
from apps.models.vector import CallPoolVector
from apps.llm.embedding import Embedding
from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB

logger = logging.getLogger(__name__)
BASE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "call"


class CallLoader(metaclass=SingletonMeta):
    """
    Call 加载器

    系统Call放在apps.scheduler.call下
    用户Call放在call下
    """

    async def _load_system_call(self) -> list[CallPool]:
        """加载系统Call"""
        call_metadata = []

        # 检查合法性
        for call_id in system_call.__all__:
            call_cls = getattr(system_call, call_id)
            call_info = call_cls.info()

            call_metadata.append(
                CallPool(
                    _id=call_id,
                    type=call_info.type,
                    name=call_info.name,
                    description=call_info.description,
                    path=f"python::apps.scheduler.call::{call_id}",
                ),
            )
        return call_metadata

    async def _load_single_call_dir(self, call_dir_name: str) -> list[CallPool]:
        """加载单个Call package"""
        call_metadata = []

        call_dir = BASE_PATH / call_dir_name
        if not (call_dir / "__init__.py").exists():
            logger.info(
                "[CallLoader] 模块 %s 不存在__init__.py文件，尝试自动创建。", call_dir)
            try:
                (Path(call_dir) / "__init__.py").touch()
            except Exception as e:
                err = f"自动创建模块文件{call_dir}/__init__.py失败：{e}。"
                raise RuntimeError(err) from e

        # 载入子包
        try:
            call_package = importlib.import_module("call." + call_dir_name)
        except Exception as e:
            err = f"载入模块call.{call_dir_name}失败：{e}。"
            raise RuntimeError(err) from e

        sys.modules["call." + call_dir_name] = call_package

        # 已载入包，处理包中每个工具
        if not hasattr(call_package, "__all__"):
            err = f"[CallLoader] 模块call.{call_dir_name}不符合模块要求，无法处理。"
            logger.info(err)
            raise ValueError(err)

        for call_id in call_package.__all__:
            try:
                call_cls = getattr(call_package, call_id)
                call_info = call_cls.info()
            except AttributeError as e:
                err = f"[CallLoader] 载入工具call.{call_dir_name}.{call_id}失败：{e}；跳过载入。"
                logger.info(err)
                continue

            cls_path = f"{call_package.service}::call.{call_dir_name}.{call_id}"
            cls_hash = shake_128(cls_path.encode()).hexdigest(8)
            call_metadata.append(
                CallPool(
                    _id=cls_hash,
                    type=CallType.PYTHON,
                    name=call_info.name,
                    description=call_info.description,
                    path=f"python::call.{call_dir_name}::{call_id}",
                ),
            )

        return call_metadata

    async def _load_all_user_call(self) -> list[CallPool]:
        """加载Python Call"""
        call_dir = BASE_PATH
        call_metadata = []

        # 载入父包
        try:
            sys.path.insert(0, str(call_dir.parent))
            if not (call_dir / "__init__.py").exists():
                logger.info(
                    "[CallLoader] 父模块 %s 不存在__init__.py文件，尝试自动创建。", call_dir)
                (Path(call_dir) / "__init__.py").touch()
            importlib.import_module("call")
        except Exception as e:
            err = f"[CallLoader] 父模块'call'创建失败：{e}；无法载入。"
            raise RuntimeError(err) from e

        # 处理每一个子包
        for call_file in Path(call_dir).rglob("*"):
            if not call_file.is_dir() or call_file.name[0] == "_":
                continue
            # 载入包
            try:
                call_metadata.extend(await self._load_single_call_dir(call_file.name))
            except RuntimeError as e:
                err = f"[CallLoader] 载入模块{call_file}失败：{e}，跳过载入。"
                logger.info(err)
                continue

        return call_metadata

    async def _delete_one(self, call_name: str) -> None:
        """删除单个Call"""
        # 从数据库中删除
        await self._delete_from_db(call_name)

        # 从Python中卸载模块
        call_dir = BASE_PATH / call_name
        if call_dir.exists():
            module_name = f"call.{call_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

    async def _delete_from_db(self, call_name: str) -> None:
        """从数据库中删除单个Call"""
        # 从MongoDB中删除
        mongo = MongoDB()
        call_collection = mongo.get_collection("call")
        node_collection = mongo.get_collection("node")
        try:
            await call_collection.delete_one({"_id": call_name})
            await node_collection.delete_many({"call_id": call_name})
        except Exception as e:
            err = f"[CallLoader] 从MongoDB删除Call失败：{e}"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 从LanceDB中删除
        while True:
            try:
                table = await LanceDB.get_table("call")
                await table.delete(f"id = '{call_name}'")
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[CallLoader] LanceDB删除call冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

    # 更新数据库

    async def _add_to_db(self, call_metadata: list[CallPool]) -> None:  # noqa: C901
        """更新数据库"""
        # 更新MongoDB
        mongo = MongoDB()
        call_collection = mongo.get_collection("call")
        node_collection = mongo.get_collection("node")
        call_descriptions = []
        try:
            for call in call_metadata:
                await call_collection.update_one(
                    {"_id": call.id}, {"$set": call.model_dump(exclude_none=True, by_alias=True)}, upsert=True,
                )
                await node_collection.insert_one(
                    NodePool(
                        _id=call.id,
                        name=call.name,
                        type=call.type,
                        description=call.description,
                        service_id="",
                        call_id=call.id,
                    ).model_dump(exclude_none=True, by_alias=True),
                )
                call_descriptions += [call.description]
        except Exception as e:
            err = "[CallLoader] 更新MongoDB失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        while True:
            try:
                table = await LanceDB.get_table("call")
                # 删除重复的ID
                for call in call_metadata:
                    await table.delete(f"id = '{call.id}'")
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[CallLoader] LanceDB插入call冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

        # 进行向量化，更新LanceDB
        call_vecs = await Embedding.get_embedding(call_descriptions)
        vector_data = []
        for i, vec in enumerate(call_vecs):
            vector_data.append(
                CallPoolVector(
                    id=call_metadata[i].id,
                    embedding=vec,
                ),
            )
        while True:
            try:
                table = await LanceDB.get_table("call")
                await table.add(vector_data)
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[CallLoader] LanceDB插入call冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

    async def load(self) -> None:
        """初始化Call信息"""
        # 清空collection
        mongo = MongoDB()
        call_collection = mongo.get_collection("call")
        node_collection = mongo.get_collection("node")
        try:
            await call_collection.delete_many({})
            await node_collection.delete_many({"service_id": ""})
        except Exception:
            logger.exception("[CallLoader] Call的collection清空失败")

        # 载入所有已知的Call信息
        try:
            sys_call_metadata = await self._load_system_call()
        except Exception as e:
            err = "[CallLoader] 载入系统Call信息失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        try:
            user_call_metadata = await self._load_all_user_call()
        except Exception:
            err = "[CallLoader] 载入用户Call信息失败"
            logger.exception(err)
            user_call_metadata = []

        # 合并Call元数据
        call_metadata = sys_call_metadata + user_call_metadata

        # 更新数据库
        await self._add_to_db(call_metadata)

    async def load_one(self, call_name: str) -> None:
        """加载单个Call"""
        try:
            call_metadata = await self._load_single_call_dir(call_name)
        except Exception as e:
            err = f"[CallLoader] 载入Call信息失败：{e}。"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 有数据时更新数据库
        if call_metadata:
            await self._add_to_db(call_metadata)
