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

from apps.entities.scheduler import CallVars
from apps.scheduler.call.core import CoreCall


class ConvertOutput(BaseModel):
    """定义Convert工具的输出"""

    text: str = Field(description="格式化后的文字信息")
    data: dict = Field(description="格式化后的结果")


class Convert(CoreCall, ret_type=ConvertOutput):
    """Convert 工具，用于对生成的文字信息和原始数据进行格式化"""

    name: str = "convert"
    description: str = "从上一步的工具的原始JSON返回结果中，提取特定字段的信息。"

    text_template: Optional[str] = Field(description="自然语言信息的格式化模板，jinja2语法", default=None)
    data_template: Optional[str] = Field(description="原始数据的格式化模板，jsonnet语法", default=None)


    async def init(self, syscall_vars: CallVars, **_kwargs: Any) -> dict[str, Any]:
        """初始化工具"""
        return {}


    async def exec(self) -> ConvertOutput:
        """调用Convert工具

        :param _slot_data: 经用户确认后的参数（目前未使用）
        :return: 提取出的字段
        """
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

        return ConvertOutput(
            text=result_message,
            data=result_data,
        )
