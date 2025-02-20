"""提取或格式化Step输出

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from datetime import datetime
from textwrap import dedent
from typing import Any, Optional

import _jsonnet
import pytz
from jinja2 import BaseLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, Field

from apps.entities.scheduler import SysCallVars
from apps.scheduler.call.core import CoreCall


class _ReformatParam(BaseModel):
    """校验Reformat Call需要的额外参数"""

    text: Optional[str] = Field(description="对生成的文字信息进行格式化，没有则不改动；jinja2语法", default=None)
    data: Optional[str] = Field(description="对生成的原始数据（JSON）进行格式化，没有则不改动；jsonnet语法", default=None)


class _ReformatOutput(BaseModel):
    """定义Reformat工具的输出"""

    message: str = Field(description="格式化后的文字信息")
    output: dict = Field(description="格式化后的结果")


class Reformat(metaclass=CoreCall, param_cls=_ReformatParam, output_cls=_ReformatOutput):
    """Reformat 工具，用于对生成的文字信息和原始数据进行格式化"""

    name: str = "reformat"
    description: str = "从上一步的工具的原始JSON返回结果中，提取特定字段的信息。"


    async def __call__(self, _slot_data: dict[str, Any]) -> _ReformatOutput:
        """调用Reformat工具

        :param _slot_data: 经用户确认后的参数（目前未使用）
        :return: 提取出的字段
        """
        # 获取必要参数
        params: _ReformatParam = getattr(self, "_params")
        syscall_vars: SysCallVars = getattr(self, "_syscall_vars")
        last_output = syscall_vars.history[-1].output_data
        # 判断用户是否给了值
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        if params.text is None:
            result_message = last_output.get("message", "")
        else:
            text_template = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=select_autoescape(),
                trim_blocks=True,
                lstrip_blocks=True,
            ).from_string(params.text)
            result_message = text_template.render(time=time, history=syscall_vars.history, question=syscall_vars.question)

        if params.data is None:
            result_data = last_output.get("output", {})
        else:
            extra_str = json.dumps({
                "time": time,
                "question": syscall_vars.question,
            }, ensure_ascii=False)
            history_str = json.dumps([item.output_data["output"] for item in syscall_vars.history if "output" in item.output_data], ensure_ascii=False)
            data_template = dedent(f"""
                local extra =  {extra_str};
                local history = {history_str};
                {params.data}
            """)
            result_data = json.loads(_jsonnet.evaluate_snippet(data_template, params.data), ensure_ascii=False)

        return _ReformatOutput(
            message=result_message,
            output=result_data,
        )
