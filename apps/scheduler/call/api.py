"""工具：API调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any, Literal, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field

from apps.constants import LOGGER
from apps.entities.scheduler import CallError, SysCallVars
from apps.manager.token import TokenManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.slot.slot import Slot


class APIParams(BaseModel):
    """API调用工具的参数"""

    full_url: str = Field(description="API接口的完整URL")
    method: Literal[
        "get", "post", "put", "delete", "patch",
    ] = Field(description="API接口的HTTP Method")
    timeout: int = Field(description="工具超时时间", default=300)
    body_override: dict[str, Any] = Field(description="固定数据", default={})
    auth: dict[str, Any] = Field(description="API鉴权信息", default={})
    input_schema: dict[str, Any] = Field(description="API请求体的JSON Schema", default={})
    service_id: Optional[str] = Field(description="服务ID")


class _APIOutput(BaseModel):
    """API调用工具的输出"""

    http_code: int = Field(description="API调用工具的HTTP返回码")
    message: str = Field(description="API调用工具的执行结果")
    output: dict[str, Any] = Field(description="API调用工具的输出")


class API(metaclass=CoreCall, param_cls=APIParams, output_cls=_APIOutput):
    """API调用工具"""

    name: str = "api"
    description: str = "根据给定的用户输入和历史记录信息，向某一个API接口发送请求、获取数据。"


    def init(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化API调用工具"""
        if kwargs["method"] == "POST":
            if "requestBody" in self._spec[2]:
                self.slot_schema, self._data_type = self._check_data_type(self._spec[2]["requestBody"]["content"])
        elif kwargs["method"] == "GET":
            if "parameters" in self._spec[2]:
                self.slot_schema = self.parameters_to_spec(self._spec[2]["parameters"])
                self._data_type = "json"
        else:
            err = "[API] HTTP method not implemented."
            raise NotImplementedError(err)


    async def __call__(self, slot_data: dict[str, Any]) -> _APIOutput:
        """调用API，然后返回LLM解析后的数据"""
        self._session = aiohttp.ClientSession()
        try:
            result = await self._call_api(slot_data)
            await self._session.close()
            return result
        except Exception as e:
            await self._session.close()
            raise RuntimeError from e


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


    async def _make_api_call(self, data: Optional[dict], files: aiohttp.FormData):  # noqa: ANN202, C901
        # 获取必要参数
        params: APIParams = getattr(self, "_params")
        syscall_vars: SysCallVars = getattr(self, "_syscall_vars")

        """调用API"""
        if self._data_type != "form":
            req_header = {
                "Content-Type": "application/json",
            }
        else:
            req_header = {}
        req_cookie = {}
        req_params = {}

        if data is None:
            data = {}

        if params.auth is not None and "type" in params.auth:
            if params.auth["type"] == "header":
                req_header.update(params.auth["args"])
            elif params.auth["type"] == "cookie":
                req_cookie.update(params.auth["args"])
            elif params.auth["type"] == "params":
                req_params.update(params.auth["args"])
            elif params.auth["type"] == "oidc":
                token = await TokenManager.get_plugin_token(
                    params.auth["domain"],
                    syscall_vars.session_id,
                    params.auth["access_token_url"],
                    int(params.auth["token_expire_time"]),
                )
                req_header.update({"access-token": token})

        if params.method in ["get", "delete"]:
            req_params.update(data)
            return self._session.request(params.method, params.full_url, params=req_params, headers=req_header, cookies=req_cookie,
                                    timeout=params.timeout)

        if params.method in ["post", "put", "patch"]:
            if self._data_type == "form":
                form_data = files
                for key, val in data.items():
                    form_data.add_field(key, val)
                return self._session.request(params.method, params.full_url, data=form_data, headers=req_header, cookies=req_cookie,
                                         timeout=params.timeout)
            return self._session.request(params.method, params.full_url, json=data, headers=req_header, cookies=req_cookie,
                                     timeout=params.timeout)

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


    async def _call_api(self, slot_data: Optional[dict[str, Any]] = None) -> _APIOutput:
        # 获取必要参数
        params: APIParams = getattr(self, "_params")
        LOGGER.info(f"调用接口{params.full_url}，请求数据为{slot_data}")

        session_context = await self._make_api_call(slot_data, aiohttp.FormData())
        async with session_context as response:
            if response.status >= status.HTTP_400_BAD_REQUEST:
                text = f"API发生错误：API返回状态码{response.status}, 原因为{response.reason}。"
                LOGGER.error(text)
                raise CallError(
                    message=text,
                    data={"api_response_data": await response.text()},
                )
            response_status = response.status
            response_data = await response.text()

        # 返回值只支持JSON的情况
        if "responses" in self._spec[2]:
            response_schema = self._spec[2]["responses"]["content"]["application/json"]["schema"]
        else:
            response_schema = {}
        LOGGER.info(f"调用接口{params.full_url}, 结果为 {response_data}")

        # 组装message
        message = f"""You called the HTTP API "{params.full_url}", which is used to "{self._spec[2]['summary']}"."""
        # 如果没有返回结果
        if response_data is None:
            return _APIOutput(
                http_code=response_status,
                output={},
                message=message + "But the API returned an empty response.",
            )

        # 如果返回值是JSON
        try:
            response_dict = json.loads(response_data)
        except Exception as e:
            err = f"返回值不是JSON：{e!s}"
            LOGGER.error(err)

        # openapi里存在有HTTP 200对应的Schema，则进行处理
        if response_schema:
            slot = Slot(response_schema)
            response_data = json.dumps(slot.process_json(response_dict), ensure_ascii=False)

        return _APIOutput(
            http_code=response_status,
            output=json.loads(response_data),
            message=message + """The API returned some data, and is shown in the "output" field below.""",
        )
