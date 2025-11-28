# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""API调用工具"""

import json
import logging
from collections.abc import AsyncGenerator
from functools import partial
from typing import Any

import httpx
from fastapi import status
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from apps.common.auth import oidc_provider
from apps.models import LanguageType
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType, ContentType, HTTPMethod
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.services.service import ServiceCenterManager
from apps.services.token import TokenManager

from .schema import APIInput, APIOutput

_logger = logging.getLogger(__name__)
SUCCESS_HTTP_CODES = [
    status.HTTP_200_OK,
    status.HTTP_201_CREATED,
    status.HTTP_202_ACCEPTED,
    status.HTTP_203_NON_AUTHORITATIVE_INFORMATION,
    status.HTTP_204_NO_CONTENT,
    status.HTTP_205_RESET_CONTENT,
    status.HTTP_206_PARTIAL_CONTENT,
    status.HTTP_207_MULTI_STATUS,
    status.HTTP_208_ALREADY_REPORTED,
    status.HTTP_226_IM_USED,
    status.HTTP_301_MOVED_PERMANENTLY,
    status.HTTP_302_FOUND,
    status.HTTP_303_SEE_OTHER,
    status.HTTP_304_NOT_MODIFIED,
    status.HTTP_307_TEMPORARY_REDIRECT,
    status.HTTP_308_PERMANENT_REDIRECT,
]


class API(CoreCall, input_model=APIInput, output_model=APIOutput):
    """API调用工具"""

    enable_filling: SkipJsonSchema[bool] = Field(description="是否需要进行自动参数填充", default=True)

    url: str = Field(description="API接口的完整URL")
    method: HTTPMethod = Field(description="API接口的HTTP Method")
    content_type: ContentType | None = Field(description="API接口的Content-Type", default=None)
    timeout: int = Field(description="工具超时时间", default=300, gt=30)

    body: dict[str, Any] = Field(description="已知的部分请求体", default={})
    query: dict[str, Any] = Field(description="已知的部分请求参数", default={})

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="API调用", description="向某一个API接口发送HTTP请求，获取数据。"),
            LanguageType.ENGLISH: CallInfo(
                name="API Call", description="Send an HTTP request to an API to obtain data.",
            ),
        }
        return i18n_info[language]

    async def _init(self, call_vars: CallVars) -> APIInput:
        """初始化API调用工具"""
        self._service_id = None
        self._user_id = call_vars.ids.user_id
        self._auth = None

        if not self.node:
            raise CallError(
                message="API工具调用时，必须指定Node",
                data={},
            )

        # 获取对应API的Service Metadata
        if self.node.serviceId:
            try:
                service_metadata = await ServiceCenterManager.get_service_metadata(
                    call_vars.ids.user_id,
                    self.node.serviceId,
                )
                # 获取Service对应的Auth
                self._auth = service_metadata.api.auth
                self._service_id = self.node.serviceId
            except Exception as e:
                raise CallError(
                    message="API接口的Service Metadata获取失败",
                    data={},
                ) from e

        return APIInput(
            url=self.url,
            method=self.method,
            query=self.query,
            body=self.body,
        )

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """调用API，然后返回LLM解析后的数据"""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        input_obj = APIInput.model_validate(input_data)
        try:
            result = await self._call_api(input_obj)
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=result.model_dump(exclude_none=True, by_alias=True),
            )
        finally:
            await self._client.aclose()

    async def _make_api_call(self, data: APIInput, files: dict[str, tuple[str, bytes, str]]) -> httpx.Response:
        """组装API请求"""
        # 获取必要参数
        if self._auth:
            req_header, req_cookie, req_params = await self._apply_auth()
        else:
            req_header = {}
            req_cookie = {}
            req_params = {}

        # 创建请求工厂
        request_factory = partial(
            self._client.request,
            method=self.method,
            url=self.url,
            cookies=req_cookie,
        )

        # 根据HTTP方法创建请求
        if self.method in [HTTPMethod.GET.value, HTTPMethod.DELETE.value]:
            # GET/DELETE 请求处理
            req_params.update(data.query)
            return await request_factory(params=req_params)

        if self.method in [HTTPMethod.POST.value, HTTPMethod.PUT.value, HTTPMethod.PATCH.value]:
            # POST/PUT/PATCH 请求处理
            if not self.content_type:
                raise CallError(message="API接口的Content-Type未指定", data={})

            # 根据Content-Type设置请求参数
            req_body = data.body
            req_header.update({"Content-Type": self.content_type})

            # 根据Content-Type决定如何发送请求体
            content_type_handlers = {
                ContentType.JSON.value: lambda body, _: {"json": body},
                ContentType.FORM_URLENCODED.value: lambda body, _: {"data": body},
                ContentType.MULTIPART_FORM_DATA.value: lambda body, files: {"data": body, "files": files},
            }

            handler = content_type_handlers.get(self.content_type)
            if not handler:
                raise CallError(message="API接口的Content-Type不支持", data={})

            request_kwargs = {}
            request_kwargs.update(handler(req_body, files))
            return await request_factory(**request_kwargs)

        raise CallError(message="API接口的HTTP Method不支持", data={})

    async def _apply_auth(self) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        """应用认证信息到请求参数中"""
        # self._auth可能是None或ServiceApiAuth类型
        # ServiceApiAuth类型包含header、cookie、query和oidc属性
        req_header = {}
        req_cookie = {}
        req_params = {}

        if self._auth:
            # 如果header列表非空
            if self._auth.header:
                for item in self._auth.header:
                    req_header[item.name] = item.value
            # 如果cookie列表非空
            if self._auth.cookie:
                for item in self._auth.cookie:
                    req_cookie[item.name] = item.value
            # 如果query列表非空
            if self._auth.query:
                for item in self._auth.query:
                    req_params[item.name] = item.value
            # 如果oidc配置存在
            if self._service_id and self._auth.oidc:
                if not self._user_id:
                    err = "[API] 未设置User ID"
                    _logger.error(err)
                    raise CallError(message=err, data={})

                token = await TokenManager.get_plugin_token(
                    self._service_id,
                    self._user_id,
                    await oidc_provider.get_access_token_url(),
                    30,
                )
                req_header.update({"access-token": token})

        return req_header, req_cookie, req_params

    async def _call_api(self, final_data: APIInput) -> APIOutput:
        """实际调用API，并处理返回值"""
        # 获取必要参数
        _logger.info("[API] 调用接口 %s，请求数据为 %s", self.url, final_data)

        files = {}  # httpx需要使用字典格式的files参数
        response = await self._make_api_call(final_data, files)

        if response.status_code not in SUCCESS_HTTP_CODES:
            text = f"API发生错误：API返回状态码{response.status_code}, 原因为{response.reason_phrase}。"
            _logger.error(text)
            raise CallError(
                message=text,
                data={"api_response_data": response.text},
            )

        response_status = response.status_code
        response_data = response.text

        _logger.info("[API] 调用接口 %s，结果为 %s", self.url, response_data)

        # 如果没有返回结果
        if not response_data:
            return APIOutput(
                http_code=response_status,
                result={},
            )

        # 如果返回值是JSON
        try:
            response_dict = json.loads(response_data)
        except Exception as e:
            raise CallError(
                message="API接口的返回值不是JSON格式",
                data={},
            ) from e

        return APIOutput(
            http_code=response_status,
            result=response_dict,
        )
