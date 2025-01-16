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
from apps.entities.flow import CallMetadata
from apps.models.mongo import MongoDB


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

    @staticmethod
    def _check_package(package_name: str) -> bool:
        """检查包是否符合要求"""
        package = sys.modules["call." + package_name]

        if not hasattr(package, "service") or not isinstance(package.service, str) or not package.service:
            return False

        if not hasattr(package, "__all__") or not isinstance(package.__all__, list) or not package.__all__:  # noqa: SIM103
            return False

        return True

    @staticmethod
    async def _load_system_call() -> list[CallMetadata]:
        """加载系统Call"""
        metadata = []

        for call_name in system_call.__all__:
            call_cls = getattr(system_call, call_name)
            if not CallLoader._check_class(call_cls):
                err = f"类{call_cls.__name__}不符合Call标准要求。"
                LOGGER.info(msg=err)
                continue

            metadata.append(
                CallMetadata(
                    _id=call_name,
                    type=CallType.SYSTEM,
                    name=call_cls.name,
                    description=call_cls.description,
                    path=call_name,
                ),
            )

        return metadata

    @classmethod
    async def _load_python_call(cls) -> list[CallMetadata]:
        """加载Python Call"""
        call_dir = Path(config["SERVICE_DIR"]) / CALL_DIR
        metadata = []

        # 检查是否存在__init__.py
        if not (call_dir / "__init__.py").exists():
            LOGGER.info(msg=f"目录{call_dir}不存在__init__.py文件。")
            (Path(call_dir) / "__init__.py").touch()

        # 载入整个包
        try:
            sys.path.insert(0, str(call_dir))
            importlib.import_module("call")
        except Exception as e:
            err = f"载入包{call_dir}失败：{e}"
            raise RuntimeError(err) from e

        # 处理每一个子包
        for call_file in Path(call_dir).rglob("*"):
            if not call_file.is_dir():
                continue

            if not cls._check_package(call_file.name):
                LOGGER.info(msg=f"包call.{call_file.name}不符合Call标准要求，跳过载入。")
                continue

            # 载入包
            try:
                call_package = importlib.import_module("call." + call_file.name)
                if not CallLoader._check_class(call_package.service):
                    LOGGER.info(msg=f"包call.{call_file.name}不符合Call标准要求，跳过载入。")
                    continue

                for call_id in call_package.__all__:
                    call_cls = getattr(call_package, call_id)
                    if not CallLoader._check_class(call_cls):
                        LOGGER.info(msg=f"类{call_cls.__name__}不符合Call标准要求，跳过载入。")
                        continue

                    metadata.append(
                        CallMetadata(
                            _id=call_id,
                            type=CallType.PYTHON,
                            name=call_cls.name,
                            description=call_cls.description,
                            path=f"{call_package.service}::call.{call_file.name}.{call_id}",
                        ),
                    )
            except Exception as e:
                err = f"载入包{call_file}失败：{e}，跳过载入"
                LOGGER.info(msg=err)
                continue

        return metadata


    @staticmethod
    async def load_one()


    @staticmethod
    async def load() -> None:
        """加载Call"""
        call_metadata = await CallLoader._load_system_call()
        call_metadata.extend(await CallLoader._load_python_call())


    @staticmethod
    async def get() -> list[CallMetadata]:
        """获取当前已知的所有Call元数据"""
        call_collection = MongoDB.get_collection("call")
        result: list[CallMetadata] = []
        try:
            cursor = call_collection.find({})
            async for item in cursor:
                result.extend([CallMetadata(**item)])
        except Exception as e:
            LOGGER.error(msg=f"获取Call元数据失败：{e}")

        return result
