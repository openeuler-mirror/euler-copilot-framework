# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""提取或格式化Step输出"""

import json
from collections.abc import AsyncGenerator
from datetime import datetime

import pytz
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.models import LanguageType
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

from .schema import ConvertInput, ConvertOutput


class Convert(CoreCall, input_model=ConvertInput, output_model=ConvertOutput):
    """Convert 工具，用于对生成的文字信息和原始数据进行格式化"""

    text_template: str | None = Field(description="自然语言信息的格式化模板，jinja2语法", default=None)
    data_template: str | None = Field(description="原始数据的格式化模板，jinja2语法", default=None)


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(
                name="模板转换",
                description="使用jinja2语法将自然语言信息和原始数据进行格式化。",
            ),
            LanguageType.ENGLISH: CallInfo(
                name="Convert",
                description="Use jinja2 syntax to format natural language information and original data.",
            ),
        }
        return i18n_info[language]

    async def _init(self, call_vars: CallVars) -> ConvertInput:
        """初始化工具"""
        await super()._init(call_vars)

        self._history = call_vars.step_data
        self._question = call_vars.question
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 获取当前时间
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        # 返回空的ConvertInput，因为输入数据来自上一步的输出
        self._extras = {
            "time": time,
            "history": self._history,
            "question": self._question,
            "background": self._sys_vars.background,
            "ids": self._sys_vars.ids,
        }
        return ConvertInput(
            text_template=self.text_template,
            data_template=self.data_template,
            extras=self._extras,
        )


    async def _exec(self) -> AsyncGenerator[CallOutputChunk, None]:
        """调用Convert工具"""
        # 处理文本模板
        result_message = ""
        if self.text_template is not None:
            try:
                text_template = self._env.from_string(self.text_template)
                result_message = text_template.render(**self._extras)
            except Exception as e:
                raise CallError(
                    message=f"文本模板渲染错误: {e!s}",
                    data={
                        "template": self.text_template,
                        "error": str(e),
                    },
                ) from e
        else:
            result_message = "未提供文本模板"

        # 处理数据模板
        result_data = {}
        if self.data_template is not None:
            try:
                data_template = self._env.from_string(self.data_template)
                rendered_data_str = data_template.render(**self._extras)
                # 尝试解析为JSON对象
                result_data = json.loads(rendered_data_str)
            except Exception as e:
                raise CallError(
                    message=f"数据模板渲染错误: {e!s}",
                    data={
                        "template": self.data_template,
                        "error": str(e),
                    },
                ) from e
        else:
            result_data = {"message": "未提供数据模板"}

        # 返回文本和数据两个部分
        yield CallOutputChunk(
            type=CallOutputType.TEXT,
            content=result_message,
        )
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=result_data,
        )
