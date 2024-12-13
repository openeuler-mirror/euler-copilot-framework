# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import os
import sys
from typing import Dict, Any, List
import json
import importlib.util
import logging

from apps.common.config import config
from apps.common.singleton import Singleton
from apps.entities.plugin import Flow, Step
from apps.scheduler.pool.pool import Pool
from apps.scheduler.call import exported

import yaml
from langchain_community.agent_toolkits.openapi.spec import reduce_openapi_spec, ReducedOpenAPISpec


OPENAPI_FILENAME = "openapi.yaml"
METADATA_FILENAME = "plugin.json"
FLOW_DIR = "flows"
LIB_DIR = "lib"

logger = logging.getLogger('gunicorn.error')


class PluginLoader:
    """
    载入单个插件的Loader。
    """
    plugin_location: str
    plugin_name: str

    def __init__(self, name: str):
        """
        初始化Loader。
        设置插件目录，随后遍历每一个
        """

        self.plugin_location = os.path.join(config["PLUGIN_DIR"], name)
        self.plugin_name = name

        metadata = self._load_metadata()
        spec = self._load_openapi_spec()
        Pool().add_plugin(name=name, spec=spec, metadata=metadata)

        if "automatic_flow" in metadata and metadata["automatic_flow"] is True:
            flows = self._single_api_to_flow(spec)
        else:
            flows = []
        flows += self._load_flow()
        Pool().add_flows(plugin=name, flows=flows)

        calls = self._load_lib()
        Pool().add_calls(plugin=name, calls=calls)

    def _load_openapi_spec(self) -> ReducedOpenAPISpec | None:
        spec_path = os.path.join(self.plugin_location, OPENAPI_FILENAME)

        if os.path.exists(spec_path):
            spec = yaml.safe_load(open(spec_path, "r", encoding="utf-8"))
            return reduce_openapi_spec(spec)
        else:
            return None

    def _load_metadata(self) -> Dict[str, Any]:
        metadata_path = os.path.join(self.plugin_location, METADATA_FILENAME)
        metadata = json.load(open(metadata_path, "r", encoding="utf-8"))
        return metadata

    @staticmethod
    def _single_api_to_flow(spec: ReducedOpenAPISpec | None = None) -> List[Dict[str, Any]]:
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
                        "endpoint": endpoint[0]
                    },
                    next="end"
                ),
                "end": Step(
                    name="end",
                    call_type="none"
                )
            }

            # 构造Flow
            flow = {
                "name": endpoint[0],
                "description": endpoint[1],
                "data": Flow(steps=step_dict)
            }

            flows.append(flow)
        return flows

    def _load_flow(self) -> List[Dict[str, Any]]:
        flow_path = os.path.join(self.plugin_location, FLOW_DIR)
        flows = []
        if os.path.isdir(flow_path):
            for item in os.listdir(flow_path):
                current_flow_path = os.path.join(flow_path, item)
                logger.info("载入Flow： {}".format(current_flow_path))

                flow_yaml = yaml.safe_load(open(current_flow_path, "r", encoding="utf-8"))

                if "." in flow_yaml["name"]:
                    raise ValueError("Flow名称包含非法字符！")

                if "on_error" in flow_yaml:
                    error_step = Step(name="error", **flow_yaml["on_error"])
                else:
                    error_step = Step(
                        name="error",
                        call_type="llm",
                        params={
                            "user_prompt": "当前工具执行发生错误，原始错误信息为：{data}. 请向用户展示错误信息，并给出可能的解决方案。\n\n背景信息：{context}"
                        }
                    )

                steps = {}
                for step in flow_yaml["steps"]:
                    steps[step["name"]] = Step(**step)

                if "next_flow" not in flow_yaml:
                    next_flow = None
                else:
                    next_flow = flow_yaml["next_flow"]

                flows.append({
                    "name": flow_yaml["name"],
                    "description": flow_yaml["description"],
                    "data": Flow(on_error=error_step, steps=steps, next_flow=next_flow),
                })
        return flows

    def _load_lib(self) -> List[Any]:
        lib_path = os.path.join(self.plugin_location, LIB_DIR)
        if os.path.isdir(lib_path):
            logger.info("载入Lib：{}".format(lib_path))
            # 插件lib载入到特定模块
            try:
                spec = importlib.util.spec_from_file_location(
                    "apps.plugins." + self.plugin_name,
                    os.path.join(self.plugin_location, "lib")
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules["apps.plugins." + self.plugin_name] = module
                spec.loader.exec_module(module)
            except Exception as e:
                logger.info(msg=f"Failed to load plugin lib: {e}")
                return []

            # 注册模块所有工具
            calls = []
            for cls in sys.modules["apps.plugins." + self.plugin_name].exported:
                try:
                    if self.check_user_class(cls):
                        calls.append(cls)
                except Exception as e:
                    logger.info(msg=f"Failed to register tools: {e}")
                    continue
            return calls
        return []

    @staticmethod
    # 用户工具不强绑定父类，而是满足要求即可
    def check_user_class(cls) -> bool:
        flag = True

        if not hasattr(cls, "name") or not isinstance(cls.name, str):
            flag = False
        if not hasattr(cls, "description") or not isinstance(cls.description, str):
            flag = False
        if not hasattr(cls, "spec") or not isinstance(cls.spec, dict):
            flag = False
        if not hasattr(cls, "__call__") or not callable(cls.__call__):
            flag = False

        if not flag:
            logger.info(msg="类{}不符合Call标准要求。".format(cls.__name__))

        return flag


# 载入全部插件
class Loader(metaclass=Singleton):
    exclude_list: List[str] = [
        ".git",
        "example"
    ]
    path: str = config["PLUGIN_DIR"]

    def __init__(self):
        raise NotImplementedError("Loader无法被实例化")

    # 载入apps/scheduler/call下面的所有工具
    @classmethod
    def load_predefined_call(cls):
        calls = []
        for item in exported:
            calls.append(item)
        try:
            Pool().add_calls(None, calls)
        except Exception as e:
            logger.info(msg=f"Failed to load predefined call: {str(e)}")

    # 首次初始化
    @classmethod
    def init(cls):
        cls.load_predefined_call()
        for item in os.scandir(cls.path):
            if item.is_dir() and item.name not in cls.exclude_list:
                try:
                    PluginLoader(name=item.name)
                except Exception as e:
                    logger.error(msg=f"Failed to load plugin: {str(e)}")

    # 后续热重载
    @classmethod
    def reload(cls):
        Pool().clean_db()
        cls.init()
