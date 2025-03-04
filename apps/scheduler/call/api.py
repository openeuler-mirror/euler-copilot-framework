"""工具：API调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any, ClassVar, Literal, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field

from apps.constants import LOGGER
from apps.entities.enum_var import ContentType, HTTPMethod
from apps.entities.scheduler import CallError, CallVars
from apps.manager.token import TokenManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.slot.slot import Slot


class APIOutput(BaseModel):
    """API调用工具的输出"""

    http_code: int = Field(description="API调用工具的HTTP返回码")
    message: str = Field(description="API调用工具的执行结果")
    output: dict[str, Any] = Field(description="API调用工具的输出")


class API(CoreCall, ret_type=APIOutput):
    """API调用工具"""

    name: ClassVar[str] = "HTTP请求"
    description: ClassVar[str] = "向某一个API接口发送HTTP请求，获取数据。"

    url: str = Field(description="API接口的完整URL")
    method: HTTPMethod = Field(description="API接口的HTTP Method")
    content_type: ContentType = Field(description="API接口的Content-Type")
    timeout: int = Field(description="工具超时时间", default=300, gt=30)
    body: dict[str, Any] = Field(description="已知的部分请求体", default={})
    auth: dict[str, Any] = Field(description="API鉴权信息", default={})


    async def exec(self, syscall_vars: CallVars, **_kwargs: Any) -> APIOutput:
        """调用API，然后返回LLM解析后的数据"""
        self._session = aiohttp.ClientSession()
        try:
            result = await self._call_api(slot_data)
            await self._session.close()
            return result
        except Exception as e:
            await self._session.close()
            raise RuntimeError from e


    async def _make_api_call(self, data: Optional[dict], files: aiohttp.FormData):  # noqa: ANN202, C901
        # 获取必要参数
        syscall_vars: CallVars = getattr(self, "_syscall_vars")

        if self.content_type != "form":
            req_header = {
                "Content-Type": ContentType.JSON.value,
            }
        else:
            req_header = {}
        req_cookie = {}
        req_params = {}

        if data is None:
            data = {}

        if self.auth is not None and "type" in self.auth:
            if self.auth["type"] == "header":
                req_header.update(self.auth["args"])
            elif self.auth["type"] == "cookie":
                req_cookie.update(self.auth["args"])
            elif self.auth["type"] == "params":
                req_params.update(self.auth["args"])
            elif self.auth["type"] == "oidc":
                token = await TokenManager.get_plugin_token(
                    self.auth["domain"],
                    syscall_vars.session_id,
                    self.auth["access_token_url"],
                    int(self.auth["token_expire_time"]),
                )
                req_header.update({"access-token": token})

        if self.method in ["get", "delete"]:
            req_params.update(data)
            return self._session.request(self.method, self.url, params=req_params, headers=req_header, cookies=req_cookie,
                                    timeout=self.timeout)

        if self.method in ["post", "put", "patch"]:
            if self.content_type == "form":
                form_data = files
                for key, val in data.items():
                    form_data.add_field(key, val)
                return self._session.request(self.method, self.url, data=form_data, headers=req_header, cookies=req_cookie,
                                         timeout=self.timeout)
            return self._session.request(self.method, self.url, json=data, headers=req_header, cookies=req_cookie,
                                     timeout=self.timeout)

        err = "Method not implemented."
        raise NotImplementedError(err)


    async def _call_api(self, slot_data: Optional[dict[str, Any]] = None) -> APIOutput:
        # 获取必要参数
        params: _APIParams = getattr(self, "_params")
        LOGGER.info(f"调用接口{params.url}，请求数据为{slot_data}")

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

        LOGGER.info(f"调用接口{params.url}, 结果为 {response_data}")

        # 组装message
        message = f"""You called the HTTP API "{params.url}", which is used to "{self._spec[2]['summary']}"."""
        # 如果没有返回结果
        if response_data is None:
            return APIOutput(
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

        return APIOutput(
            http_code=response_status,
            output=json.loads(response_data),
            message=message + "The API returned some data, and is shown in the 'output' field below.",
        )
