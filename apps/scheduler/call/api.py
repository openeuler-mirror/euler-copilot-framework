"""工具：API调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any, Literal, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field

from apps.constants import LOGGER
from apps.entities.plugin import CallError, SysCallVars
from apps.manager.token import TokenManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.slot.slot import Slot


class _APIParams(BaseModel):
    full_url: str = Field(description="API接口的完整URL")
    method: Literal[
        "GET", "POST",
    ] = Field(description="API接口的HTTP Method")
    timeout: int = Field(description="工具超时时间", default=300)
    input_data: dict[str, Any] = Field(description="固定数据", default={})
    service_id: Optional[str] = Field(description="服务ID")


class _APIOutput(BaseModel):
    """API调用工具的输出"""

    output: dict[str, Any] = Field(description="API调用工具的输出")


class API(CoreCall):
    """API调用工具"""

    name: str = "api"
    description: str = "根据给定的用户输入和历史记录信息，向某一个API接口发送请求、获取数据。"
    params: type[_APIParams] = _APIParams


    async def init(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化API调用工具"""
        # 插件鉴权
        self._auth = json.loads(str(plugin_data.auth))
        # 从spec中找出该接口对应的spec
        for item in full_spec.endpoints:
            name, _, _ = item
            if name == self.params.endpoint:
                self._spec = item
        if not hasattr(self, "_spec"):
            err = "[API] Endpoint not found."
            raise ValueError(err)

        if method == "POST":
            if "requestBody" in self._spec[2]:
                self.slot_schema, self._data_type = self._check_data_type(self._spec[2]["requestBody"]["content"])
        elif method == "GET":
            if "parameters" in self._spec[2]:
                self.slot_schema = self.parameters_to_spec(self._spec[2]["parameters"])
                self._data_type = "json"
        else:
            err = "[API] HTTP method not implemented."
            raise NotImplementedError(err)


    async def call(self, slot_data: dict[str, Any]) -> CallResult:
        """调用API，然后返回LLM解析后的数据"""
        self._session = aiohttp.ClientSession()
        try:
            result = await self._call_api(method, url, slot_data)
            await self._session.close()
            return result
        except Exception as e:
            await self._session.close()
            raise RuntimeError from e


    @staticmethod
    def _process_response_schema(response_data: str, response_schema: dict[str, Any]) -> str:
        """对API返回值进行逐个字段处理"""
        # 工具执行报错，此时为错误信息，不予处理
        try:
            response_dict = json.loads(response_data)
        except Exception:
            return response_data

        # openapi里没有HTTP 200对应的Schema，不予处理
        if not response_schema:
            return response_data

        slot = Slot(response_schema)
        return json.dumps(slot.process_json(response_dict), ensure_ascii=False)


    @staticmethod
    def parameters_to_spec(raw_schema: list[dict[str, Any]]) -> dict[str, Any]:
        """将OpenAPI中GET接口List形式的请求体Spec转换为JSON Schema"""
        schema = {
            "type": "object",
            "required": [],
            "properties": {},
        }
        for item in raw_schema:
            if item["required"]:
                schema["required"].append(item["name"])
            schema["properties"][item["name"]] = {}
            schema["properties"][item["name"]]["description"] = item["description"]
            for key, val in item["schema"].items():
                schema["properties"][item["name"]][key] = val
        return schema


    @staticmethod
    def process(
        response_data: Optional[str], url: str, usage: str, response_schema: dict[str, Any],
    ) -> CallResult:
        """对返回值进行整体处理"""
        # 如果结果太长，不使用大模型进行总结；否则使用大模型生成自然语言总结
        if response_data is None:
            return CallResult(
                output={},
                output_schema={},
                message=f"调用接口{url}成功，但返回值为空。",
            )

        if len(response_data) > MAX_API_RESPONSE_LENGTH:
            response_data = response_data[:MAX_API_RESPONSE_LENGTH]
            response_data = response_data[:response_data.rfind(",") - 1]
            response_data = untrunc.complete(response_data)

        response_data = APISanitizer._process_response_schema(response_data, response_schema)

        message = dedent(f"""调用API从外部数据源获取了数据。API和数据源的描述为：{usage}""")

        return CallResult(
            output=json.loads(response_data),
            output_schema=response_schema,
            message=message,
        )


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
                    self._syscall_vars.session_id,
                    self._auth["access_token_url"],
                    int(self._auth["token_expire_time"]),
                )
                header.update({"access-token": token})

        if self._params.method == "GET":
            params.update(data)
            return self._session.get(self._server + url, params=params, headers=header, cookies=cookie,
                                    timeout=self.params.timeout)
        if method == "POST":
            if self._data_type == "form":
                form_data = files
                for key, val in data.items():
                    form_data.add_field(key, val)
                return self._session.post(self._server + url, data=form_data, headers=header, cookies=cookie,
                                         timeout=self.params.timeout)
            return self._session.post(self._server + url, json=data, headers=header, cookies=cookie,
                                     timeout=self.params.timeout)

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
                text = f"API发生错误：API返回状态码{response.status}, 原因为{response.reason}。"
                LOGGER.error(text)
                raise CallError(
                    message=text,
                    data={"api_response_data": await response.text()},
                )
            response_data = await response.text()

        # 返回值只支持JSON的情况
        if "responses" in self._spec[2]:
            response_schema = self._spec[2]["responses"]["content"]["application/json"]["schema"]
        else:
            response_schema = {}
        LOGGER.info(f"调用接口{url}, 结果为 {response_data}")

        return self.process(response_data, url, self._spec[1], response_schema)
