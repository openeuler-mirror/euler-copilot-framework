"""Call 加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import importlib
import sys
from hashlib import shake_128
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

import apps.scheduler.call as system_call
from apps.common.config import config
from apps.constants import CALL_DIR, LOGGER
from apps.entities.enum_var import CallType
from apps.entities.pool import CallPool
from apps.entities.vector import CallPoolVector
from apps.models.mongo import MongoDB
from apps.models.postgres import PostgreSQL


class CallLoader:
    """Call 加载器

    系统Call放在apps.scheduler.call下
    用户Call放在call下
    """

    @staticmethod
    def _check_class(user_cls) -> bool:  # noqa: ANN001
        """检查用户类是否符合Call标准要求"""
        flag = True

        if not hasattr(user_cls, "name") or not isinstance(user_cls.name, str):
            flag = False
        if not hasattr(user_cls, "description") or not isinstance(user_cls.description, str):
            flag = False
        if not hasattr(user_cls, "output_schema") or not isinstance(user_cls.output_schema, dict):
            flag = False
        if not hasattr(user_cls, "params_schema") or not isinstance(user_cls.params_schema, dict):
            flag = False
        if not hasattr(user_cls, "init") or not callable(user_cls.init):
            flag = False
        if not callable(user_cls) or not callable(user_cls.__call__):
            flag = False

        return flag


    async def _load_system_call(self) -> list[CallPool]:
        """加载系统Call"""
        call_metadata = []

        # 检查合法性
        for call_id in system_call.__all__:
            call_cls = getattr(system_call, call_id)
            if not self._check_class(call_cls):
                err = f"系统类{call_cls.__name__}不符合Call标准要求。"
                LOGGER.info(msg=err)
                continue

            call_metadata.append(
                CallPool(
                    _id=call_id,
                    type=CallType.SYSTEM,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=f"python::apps.scheduler.call::{call_id}",
                ),
            )

        return call_metadata


    async def _load_single_call_dir(self, call_name: str) -> list[CallPool]:
        """加载单个Call package"""
        call_metadata = []

        call_dir = Path(config["SEMANTICS_DIR"]) / CALL_DIR / call_name
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

        sys.modules["call." + call_name] = call_package

        # 已载入包，处理包中每个工具
        if not hasattr(call_package, "__all__"):
            err = f"模块call.{call_name}不符合模块要求，无法处理。"
            LOGGER.info(msg=err)
            raise ValueError(err)

        for call_id in call_package.__all__:
            try:
                call_cls = getattr(call_package, call_id)
            except Exception as e:
                err = f"载入工具call.{call_name}.{call_id}失败：{e}；跳过载入。"
                LOGGER.info(msg=err)
                continue

            if not self._check_class(call_cls):
                err = f"工具call.{call_name}.{call_id}不符合标准要求；跳过载入。"
                LOGGER.info(msg=err)
                continue

            cls_path = f"{call_package.service}::call.{call_name}.{call_id}"
            cls_hash = shake_128(cls_path.encode()).hexdigest(8)
            call_metadata.append(
                CallPool(
                    _id=cls_hash,
                    type=CallType.PYTHON,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=f"python::call.{call_name}::{call_id}",
                ),
            )

        return call_metadata

    async def _load_all_user_call(self) -> list[CallPool]:
        """加载Python Call"""
        call_dir = Path(config["SEMANTICS_DIR"]) / CALL_DIR
        call_metadata = []

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
                call_metadata.extend(await self._load_single_call_dir(call_file.name))
            except Exception as e:
                err = f"载入模块{call_file}失败：{e}，跳过载入。"
                LOGGER.info(msg=err)
                continue

        return call_metadata


    # TODO: 动态卸载
    async def _delete_one(self, call_name: str) -> None:
        """删除单个Call"""
        pass


    async def _delete_from_db(self, call_name: str) -> None:
        """从数据库中删除单个Call"""
        pass


    # 更新数据库
    async def _add_to_db(self, call_metadata: list[CallPool]) -> None:
        """更新数据库"""
        # 更新MongoDB
        call_collection = MongoDB.get_collection("call")
        call_descriptions = []
        try:
            for call in call_metadata:
                await call_collection.update_one({"_id": call.id}, {"$set": call.model_dump(exclude_none=True, by_alias=True)}, upsert=True)
                call_descriptions += [call.description]
        except Exception as e:
            err = f"更新MongoDB失败：{e}"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        # 进行向量化，更新PostgreSQL
        session = await PostgreSQL.get_session()
        call_vecs = await PostgreSQL.get_embedding(call_descriptions)
        for i, data in enumerate(call_vecs):
            insert_stmt = insert(CallPoolVector).values(
                id=call_metadata[i].id,
                embedding=data,
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={"embedding": data},
            )
            await session.execute(insert_stmt)
        await session.commit()
        await session.aclose()


    async def load(self) -> None:
        """初始化Call信息"""
        # 清空collection
        call_collection = MongoDB.get_collection("call")
        try:
            await call_collection.delete_many({})
        except Exception as e:
            LOGGER.error(msg=f"Call的collection清空失败：{e}")

        # 载入所有已知的Call信息
        try:
            sys_call_metadata = await self._load_system_call()
        except Exception as e:
            err = f"载入系统Call信息失败：{e}；停止运行。"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        try:
            user_call_metadata = await self._load_all_user_call()
        except Exception as e:
            err = f"载入用户Call信息失败：{e}；只可使用基本功能。"
            LOGGER.error(msg=err)
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
            err = f"载入Call信息失败：{e}。"
            LOGGER.error(msg=err)
            raise RuntimeError(err) from e

        # 有数据时更新数据库
        if call_metadata:
            await self._add_to_db(call_metadata)
