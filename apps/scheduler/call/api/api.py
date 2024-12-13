# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# 工具：API调用

from __future__ import annotations

import json
from typing import Dict, Tuple, Any, Union
import logging

from apps.scheduler.call.core import CoreCall, CallParams
from apps.scheduler.gen_json import check_upload_file
from apps.scheduler.files import Files, choose_file
from apps.scheduler.utils import Json
from apps.scheduler.pool.pool import Pool
from apps.manager.plugin_token import PluginTokenManager
from apps.scheduler.call.api.sanitizer import APISanitizer

from pydantic import Field
from langchain_community.agent_toolkits.openapi.spec import ReducedOpenAPISpec
import aiohttp


logger = logging.getLogger('gunicorn.error')


class APIParams(CallParams):
    plugin: str = Field(description="Plugin名称")
    endpoint: str = Field(description="API接口HTTP Method 与 URI")
    timeout: int = Field(description="工具超时时间", default=300)
    retry: int = Field(description="调用发生错误时，最大的重试次数。", default=3)


class API(CoreCall):
    name = "api"
    description = "API调用工具，用于根据给定的用户输入和历史记录信息，向某一个API接口发送请求、获取数据。"
    params_obj: APIParams

    server: str
    data_type: Union[str, None] = None
    session: aiohttp.ClientSession
    usage: str
    spec: ReducedOpenAPISpec
    auth: Dict[str, Any]
    session_id: str

    def __init__(self, params: Dict[str, Any]):
        self.params_obj = APIParams(**params)

    async def call(self, fixed_params: Union[Dict[str, Any], None] = None):
        # 参数
        method, url = self.params_obj.endpoint.split()

        # 从Pool中拿到Plugin的全部OpenAPI Spec
        plugin_metadata = Pool().get_plugin(self.params_obj.plugin)
        self.spec = Pool.deserialize_data(plugin_metadata.spec, plugin_metadata.signature)
        self.auth = json.loads(plugin_metadata.auth)
        self.session_id = self.params_obj.session_id

        # 服务器地址，只支持服务器为1个的情况
        self.server = self.spec.servers[0]["url"].rstrip("/")

        spec = None
        # 从spec中找出该接口对应的spec
        for item in self.spec.endpoints:
            name, description, out = item
            if name == self.params_obj.endpoint:
                spec = item
        if spec is None:
            raise ValueError("Endpoint not found!")

        self.usage = spec[1]

        # 调用，然后返回数据
        self.session = aiohttp.ClientSession()
        try:
            result = await self._call_api(method, url, spec)
            await self.session.close()
            return result
        except Exception as e:
            await self.session.close()
            raise Exception(e)

    async def _make_api_call(self, method: str, url: str, data: dict, files: aiohttp.FormData):
        if self.data_type != "form":
            header = {
                "Content-Type": "application/json",
            }
        else:
            header = {}
        cookie = {}
        params = {}

        if self.auth is not None and "type" in self.auth:
            if self.auth["type"] == "header":
                header.update(self.auth["args"])
            elif self.auth["type"] == "cookie":
                cookie.update(self.auth["args"])
            elif self.auth["type"] == "params":
                params.update(self.auth["args"])
            elif self.auth["type"] == "oidc":
                header.update({
                    "access-token": PluginTokenManager.get_plugin_token(
                        self.auth["domain"],
                        self.session_id,
                        self.auth["access_token_url"],
                        int(self.auth["token_expire_time"])
                    )
                })

        if method == "GET":
            params.update(data)
            return self.session.get(self.server + url, params=params, headers=header, cookies=cookie,
                                    timeout=self.params_obj.timeout)
        elif method == "POST":
            if self.data_type == "form":
                form_data = files
                for key, val in data.items():
                    form_data.add_field(key, val)
                return self.session.post(self.server + url, data=form_data, headers=header, cookies=cookie,
                                         timeout=self.params_obj.timeout)
            else:
                return self.session.post(self.server + url, json=data, headers=header, cookies=cookie,
                                         timeout=self.params_obj.timeout)
        else:
            raise NotImplementedError("Method not implemented.")

    def _check_data_type(self, spec: dict) -> dict:
        if "application/json" in spec:
            self.data_type = "json"
            return spec["application/json"]["schema"]
        if "x-www-form-urlencoded" in spec:
            self.data_type = "form"
            return spec["x-www-form-urlencoded"]["schema"]
        if "multipart/form-data" in spec:
            self.data_type = "form"
            return spec["multipart/form-data"]["schema"]
        else:
            raise NotImplementedError("Data type not implemented.")

    def _file_to_lists(self, spec: Dict[str, Any]) -> aiohttp.FormData:
        file_form = aiohttp.FormData()

        if self.params_obj.files is None:
            return file_form

        file_names = []
        for file in self.params_obj.files:
            file_names.append(Files.get_by_id(file)["name"])

        file_spec = check_upload_file(spec, file_names)
        selected_file = choose_file(file_names, file_spec, self.params_obj.question, self.params_obj.background, self.usage)

        for key, val in json.loads(selected_file).items():
            if isinstance(val, str):
                file_form.add_field(key, open(Files.get_by_name(val)["path"], "rb"), filename=val)
            else:
                for item in val:
                    file_form.add_field(key, open(Files.get_by_name(item)["path"], "rb"), filename=item)
        return file_form

    async def _call_api(self, method: str, url: str, spec: Tuple[str, str, dict]):
        param_spec = {}

        if method == "POST":
            if "requestBody" in spec[2]:
                param_spec = self._check_data_type(spec[2]["requestBody"]["content"])
        elif method == "GET":
            if "parameters" in spec[2]:
                param_spec = APISanitizer.parameters_to_spec(spec[2]["parameters"])
        else:
            raise NotImplementedError("HTTP method not implemented.")

        if param_spec != {}:
            json_data = await Json().generate_json(self.params_obj.background, self.params_obj.question, param_spec)
        else:
            json_data = {}

        if "properties" in param_spec:
            file_list = self._file_to_lists(param_spec["properties"])
        else:
            file_list = []

        logger.info(f"调用接口{url}，请求数据为{json_data}")
        session_context = await self._make_api_call(method, url, json_data, file_list)
        async with session_context as response:
            if response.status != 200:
                response_data = "API发生错误：API返回状态码{}, 详细原因为{}，附加信息为{}。".format(response.status, response.reason, await response.text())
            else:
                response_data = await response.text()

        # 返回值只支持JSON的情况
        if "responses" in spec[2]:
            response_schema = spec[2]["responses"]["content"]["application/json"]["schema"]
        else:
            response_schema = {}
        logger.info(f"调用接口{url}, 结果为 {response_data}")

        result = APISanitizer.process_response_data(response_data, url, self.params_obj.question, self.usage, response_schema)
        return result
