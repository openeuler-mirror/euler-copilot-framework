"""Pool：载入器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from typing import Any, ClassVar, Optional

import yaml
from langchain_community.agent_toolkits.openapi.spec import (
    ReducedOpenAPISpec,
    reduce_openapi_spec,
)

import apps.scheduler.call as system_call
from apps.common.config import config
from apps.common.singleton import Singleton
from apps.constants import LOGGER
from apps.entities.plugin import Flow, NextFlow, Step
from apps.scheduler.pool.pool import Pool

OPENAPI_FILENAME = "openapi.yaml"
METADATA_FILENAME = "plugin.json"
FLOW_DIR = "flows"
LIB_DIR = "lib"


class PluginLoader:
    """载入单个插件的Loader。"""

    def __init__(self, plugin_id: str) -> None:
        """初始化Loader。

        设置插件目录，随后遍历每一个
        """
        self._plugin_location = Path(config["PLUGIN_DIR"]) / plugin_id
        self.plugin_name = plugin_id

        metadata = self._load_metadata()
        spec = self._load_openapi_spec()
        Pool().add_plugin(plugin_id=plugin_id, spec=spec, metadata=metadata)

        if "automatic_flow" in metadata and metadata["automatic_flow"] is True:
            flows = self._single_api_to_flow(spec)
        else:
            flows = []
        flows += self._load_flow()
        Pool().add_flows(plugin=plugin_id, flows=flows)

        calls = self._load_lib()
        Pool().add_calls(plugin=plugin_id, calls=calls)

    def _load_openapi_spec(self) -> Optional[ReducedOpenAPISpec]:
        spec_path = self._plugin_location / OPENAPI_FILENAME

        if spec_path.exists():
            with Path(spec_path).open(encoding="utf-8") as f:
                spec = yaml.safe_load(f)
            return reduce_openapi_spec(spec)
        return None

    def _load_metadata(self) -> dict[str, Any]:
        metadata_path = self._plugin_location / METADATA_FILENAME
        return json.load(Path(metadata_path).open(encoding="utf-8"))

    @staticmethod
    def _single_api_to_flow(spec: Optional[ReducedOpenAPISpec] = None) -> list[dict[str, Any]]:
        if not spec:
            return []

        flows = []
        for endpoint in spec.endpoints:
            # 构造Step
            step_dict = {
                "start": Step(
                    name="start",
                    call_type="api",
                    params={
                        "endpoint": endpoint[0],
                    },
                    next="end",
                ),
                "end": Step(
                    name="end",
                    call_type="none",
                ),
            }

            # 构造Flow
            flow = {
                "id": endpoint[0],
                "description": endpoint[1],
                "data": Flow(steps=step_dict),
            }

            flows.append(flow)
        return flows

    def _load_flow(self) -> list[dict[str, Any]]:
        flow_path = self._plugin_location / FLOW_DIR
        flows = []
        if flow_path.is_dir():
            for current_flow_path in flow_path.iterdir():
                LOGGER.info(f"载入Flow： {current_flow_path}")

                with Path(current_flow_path).open(encoding="utf-8") as f:
                    flow_yaml = yaml.safe_load(f)

                if "/" in flow_yaml["id"]:
                    err = "Flow名称包含非法字符！"
                    raise ValueError(err)

                if "on_error" in flow_yaml:
                    error_step = Step(name="error", **flow_yaml["on_error"])
                else:
                    error_step = Step(
                        name="error",
                        call_type="llm",
                        params={
                            "user_prompt": "当前工具执行发生错误，原始错误信息为：{data}. 请向用户展示错误信息，并给出可能的解决方案。\n\n背景信息：{context}",
                        },
                    )

                steps = {}
                for step in flow_yaml["steps"]:
                    steps[step["name"]] = Step(**step)

                if "next_flow" not in flow_yaml:
                    next_flow = None
                else:
                    next_flow = []
                    for next_flow_item in flow_yaml["next_flow"]:
                        next_flow.append(NextFlow(
                            id=next_flow_item["id"],
                            question=next_flow_item["question"],
                        ))
                flows.append({
                    "id": flow_yaml["id"],
                    "description": flow_yaml["description"],
                    "data": Flow(on_error=error_step, steps=steps, next_flow=next_flow),
                })
        return flows

    def _load_lib(self) -> list[Any]:
        lib_path = self._plugin_location / LIB_DIR
        if lib_path.is_dir():
            LOGGER.info(f"载入Lib：{lib_path}")
            # 插件lib载入到特定模块
            try:
                spec = importlib.util.spec_from_file_location(
                    "apps.plugins." + self.plugin_name,
                    lib_path,
                )

                if spec is None:
                    return []

                module = importlib.util.module_from_spec(spec)
                sys.modules["apps.plugins." + self.plugin_name] = module

                loader = spec.loader
                if loader is None:
                    return []

                loader.exec_module(module)
            except Exception as e:
                LOGGER.info(msg=f"Failed to load plugin lib: {e}")
                return []

            # 注册模块所有工具
            calls = []
            for cls in sys.modules["apps.plugins." + self.plugin_name].exported:
                try:
                    if self.check_user_class(cls):
                        calls.append(cls)
                except Exception as e:  # noqa: PERF203
                    LOGGER.info(msg=f"Failed to register tools: {e}")
            return calls
        return []

    @staticmethod
    def check_user_class(user_cls) -> bool:  # noqa: ANN001
        """检查用户类是否符合Call标准要求"""
        flag = True

        if not hasattr(user_cls, "name") or not isinstance(user_cls.name, str):
            flag = False
        if not hasattr(user_cls, "description") or not isinstance(user_cls.description, str):
            flag = False
        if not hasattr(user_cls, "spec") or not isinstance(user_cls.spec, dict):
            flag = False
        if not callable(user_cls) or not callable(user_cls.__call__):
            flag = False

        if not flag:
            LOGGER.info(msg=f"类{user_cls.__name__}不符合Call标准要求。")

        return flag


class Loader(metaclass=Singleton):
    """载入全部插件"""

    exclude_list: ClassVar[list[str]] = [
        ".git",
        "example",
    ]
    path: str = config["PLUGIN_DIR"]

    @classmethod
    def load_predefined_call(cls) -> None:
        """载入apps/scheduler/call下面的所有工具"""
        calls = [getattr(system_call, name) for name in system_call.__all__]
        try:
            Pool().add_calls(None, calls)
        except Exception as e:
            LOGGER.info(msg=f"Failed to load predefined call: {e!s}\n{traceback.format_exc()}")

    @classmethod
    def init(cls) -> None:
        """初始化插件"""
        cls.load_predefined_call()
        for item in Path(cls.path).iterdir():
            if item.is_dir() and item.name not in cls.exclude_list:
                try:
                    PluginLoader(plugin_id=item.name)
                except Exception as e:
                    LOGGER.info(msg=f"Failed to load plugin: {e!s}\n{traceback.format_exc()}")

    @classmethod
    def reload(cls) -> None:
        """热重载插件"""
        Pool().clean_db()
        cls.init()
