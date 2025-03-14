"""提取或格式化Step输出

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from datetime import datetime
from textwrap import dedent
from typing import Any, ClassVar, Optional

import _jsonnet
import pytz
from jinja2 import BaseLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, Field

from apps.entities.plugin import CallResult, SysCallVars
from apps.scheduler.call.core import CoreCall


class _ReformatParam(BaseModel):
    """校验Reformat Call需要的额外参数"""

    text: Optional[str] = Field(description="对生成的文字信息进行格式化，没有则不改动；jinja2语法", default=None)
    data: Optional[str] = Field(description="对生成的原始数据（JSON）进行格式化，没有则不改动；jsonnet语法", default=None)


class Extract(CoreCall):
    """Reformat 工具，用于对生成的文字信息和原始数据进行格式化"""

    name: str = "reformat"
    description: str = "从上一步的工具的原始JSON返回结果中，提取特定字段的信息。"
    params_schema: ClassVar[dict[str, Any]] = _ReformatParam.model_json_schema()


    def __init__(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化Reformat工具"""
        self._core_params = syscall_vars
        self._params = _ReformatParam.model_validate(kwargs)
        self._last_output = CallResult(**self._core_params.history[-1].output_data)
        # 初始化Slot Schema
        self.slot_schema = {}


    async def call(self, _slot_data: dict[str, Any]) -> CallResult:
        """调用Reformat工具

        :param _slot_data: 经用户确认后的参数（目前未使用）
        :return: 提取出的字段
        """
        # 判断用户是否给了值
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        if self._params.text is None:
            result_message = self._last_output.message
        else:
            text_template = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            ).from_string(self._params.text)
            result_message = text_template.render(time=time, history=self._core_params.history, question=self._core_params.question)

        if self._params.data is None:
            result_data = self._last_output.output
        else:
            extra_str = json.dumps({
                "time": time,
                "question": self._core_params.question,
            }, ensure_ascii=False)
            history_str = json.dumps([CallResult(**item.output_data).output for item in self._core_params.history], ensure_ascii=False)
            data_template = dedent(f"""
                local extra =  {extra_str};
                local history = {history_str};
                {self._params.data}
            """)
            result_data = json.loads(_jsonnet.evaluate_snippet(data_template, self._params.data), ensure_ascii=False)

        return CallResult(
            message=result_message,
            output=result_data,
            output_schema={
                "type": "object",
                "description": "格式化后的结果",
            },
        )
