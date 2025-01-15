"""工具：API调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any, ClassVar, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field

from apps.constants import LOGGER
from apps.entities.plugin import CallError, CallResult, SysCallVars
from apps.manager.token import TokenManager
from apps.scheduler.call.api.sanitizer import APISanitizer
from apps.scheduler.call.core import CoreCall
from apps.scheduler.pool.pool import Pool


class _APIParams(BaseModel):
    endpoint: str = Field(description="API接口HTTP Method 与 URI")
    timeout: int = Field(description="工具超时时间", default=300)


class API(CoreCall):
    """API调用工具"""

    name: str = "api"
    description: str = "根据给定的用户输入和历史记录信息，向某一个API接口发送请求、获取数据。"
    params_schema: ClassVar[dict[str, Any]] = _APIParams.model_json_schema()


    def __init__(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化API调用工具"""
        # 固定参数
        self._core_params = syscall_vars
        self._params = _APIParams.model_validate(kwargs)
        # 初始化Slot Schema
        self.slot_schema = {}

        # 额外参数
        if "plugin_id" not in self._core_params.extra:
            err = "[API] plugin_id not in extra_data"
            raise ValueError(err)
        plugin_name: str = self._core_params.extra["plugin_id"]

        method, _ = self._params.endpoint.split(" ")
        plugin_data = Pool().get_plugin(plugin_name)
        if plugin_data is None:
            err = f"[API] 插件{plugin_name}不存在！"
            raise ValueError(err)

        # 插件鉴权
        self._auth = json.loads(str(plugin_data.auth))
        # 插件OpenAPI Spec
        full_spec = Pool.deserialize_data(plugin_data.spec, str(plugin_data.signature))  # type: ignore[arg-type]
        # 服务器地址，只支持服务器为1个的情况
        self._server = full_spec.servers[0]["url"].rstrip("/")
        # 从spec中找出该接口对应的spec
        for item in full_spec.endpoints:
            name, _, _ = item
            if name == self._params.endpoint:
                self._spec = item
        if not hasattr(self, "_spec"):
            err = "[API] Endpoint not found."
            raise ValueError(err)

        if method == "POST":
            if "requestBody" in self._spec[2]:
                self.slot_schema, self._data_type = self._check_data_type(self._spec[2]["requestBody"]["content"])
        elif method == "GET":
            if "parameters" in self._spec[2]:
                self.slot_schema = APISanitizer.parameters_to_spec(self._spec[2]["parameters"])
                self._data_type = "json"
        else:
            err = "[API] HTTP method not implemented."
            raise NotImplementedError(err)


    async def call(self, slot_data: dict[str, Any]) -> CallResult:
        """调用API，然后返回LLM解析后的数据"""
        method, url = self._params.endpoint.split(" ")
        self._session = aiohttp.ClientSession()
        try:
            result = await self._call_api(method, url, slot_data)
            await self._session.close()
            return result
        except Exception as e:
            await self._session.close()
            raise RuntimeError from e


    async def _make_api_call(self, method: str, url: str, data: Optional[dict], files: aiohttp.FormData):  # noqa: ANN202, C901
        """调用API"""
        if self._data_type != "form":
            header = {
                "Content-Type": "application/json",
            }
        else:
            header = {}
        cookie = {}
        params = {}

        if data is None:
            data = {}

        if self._auth is not None and "type" in self._auth:
            if self._auth["type"] == "header":
                header.update(self._auth["args"])
            elif self._auth["type"] == "cookie":
                cookie.update(self._auth["args"])
            elif self._auth["type"] == "params":
                params.update(self._auth["args"])
            elif self._auth["type"] == "oidc":
                token = await TokenManager.get_plugin_token(
                    self._auth["domain"],
                    self._core_params.session_id,
                    self._auth["access_token_url"],
                    int(self._auth["token_expire_time"]),
                )
                header.update({"access-token": token})

        if method == "GET":
            params.update(data)
            return self._session.get(self._server + url, params=params, headers=header, cookies=cookie,
                                    timeout=self._params.timeout)
        if method == "POST":
            if self._data_type == "form":
                form_data = files
                for key, val in data.items():
                    form_data.add_field(key, val)
                return self._session.post(self._server + url, data=form_data, headers=header, cookies=cookie,
                                         timeout=self._params.timeout)
            return self._session.post(self._server + url, json=data, headers=header, cookies=cookie,
                                     timeout=self._params.timeout)

        err = "Method not implemented."
        raise NotImplementedError(err)

    @staticmethod
    def _check_data_type(spec: dict) -> tuple[dict[str, Any], str]:
        if "application/json" in spec:
            return spec["application/json"]["schema"], "json"
        if "x-www-form-urlencoded" in spec:
            return spec["x-www-form-urlencoded"]["schema"], "form"
        if "multipart/form-data" in spec:
            return spec["multipart/form-data"]["schema"], "form"

        err = "Data type not implemented."
        raise NotImplementedError(err)

    async def _call_api(self, method: str, url: str, slot_data: Optional[dict[str, Any]] = None) -> CallResult:
        LOGGER.info(f"调用接口{url}，请求数据为{slot_data}")
        session_context = await self._make_api_call(method, url, slot_data, aiohttp.FormData())
        async with session_context as response:
            if response.status >= status.HTTP_400_BAD_REQUEST:
                raise CallError(
                    message=f"API发生错误：API返回状态码{response.status}, 原因为{response.reason}。",
                    data={"api_response_data": await response.text()},
                )
            response_data = await response.text()

        # 返回值只支持JSON的情况
        if "responses" in self._spec[2]:
            response_schema = self._spec[2]["responses"]["content"]["application/json"]["schema"]
        else:
            response_schema = {}
        LOGGER.info(f"调用接口{url}, 结果为 {response_data}")

        return APISanitizer.process(response_data, url, self._spec[1], response_schema)
