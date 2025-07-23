# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""图表生成工具"""

import json
from collections.abc import AsyncGenerator
from typing import Any

from anyio import Path
from pydantic import Field

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.graph.schema import RenderFormat, RenderInput, RenderOutput
from apps.scheduler.call.graph.style import RenderStyle
from apps.schemas.enum_var import CallOutputType, CallType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)


class Graph(CoreCall, input_model=RenderInput, output_model=RenderOutput):
    """Render Call，用于将SQL Tool查询出的数据转换为图表"""

    dataset_key: str = Field(description="图表的数据来源（字段名）", default="")


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(
            name="图表", 
            type=CallType.TRANSFORM,
            description="将SQL查询出的数据转换为图表"
        )


    async def _init(self, call_vars: CallVars) -> RenderInput:
        """初始化Render Call，校验参数，读取option模板"""
        try:
            option_location = Path(__file__).parent / "option.json"
            f = await Path(option_location).open(encoding="utf-8")
            data = await f.read()
            self._option_template = json.loads(data)
            await f.aclose()
        except Exception as e:
            raise CallError(message=f"图表模板读取失败：{e!s}", data={}) from e

        # 获取数据
        if not self.dataset_key:
            last_step_id = call_vars.history_order[-1]
            self.dataset_key = f"{last_step_id}/dataset"
        data = self._extract_history_variables(self.dataset_key, call_vars.history)

        return RenderInput(
            question=call_vars.question,
            data=data,
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行Render Call"""
        data = RenderInput(**input_data)

        # 判断数据格式是否满足要求
        # 样例：[{'openeuler_version': 'openEuler-22.03-LTS-SP2', '软件数量': 10}]
        malformed = True
        if isinstance(data.data, list) and len(data.data) > 0 and isinstance(data.data[0], dict):
            malformed = False

        # 将执行SQL工具查询到的数据转换为特定格式
        if malformed:
            raise CallError(
                message="数据格式错误，无法生成图表！",
                data={"data": data.data},
            )

        # 对少量数据进行处理
        processed_data = data.data
        column_num = len(processed_data[0]) - 1
        if column_num == 0:
            processed_data = Graph._separate_key_value(processed_data)
            column_num = 1

        # 该格式满足ECharts DataSource要求，与option模板进行拼接
        self._option_template["dataset"]["source"] = processed_data

        try:
            style_obj = RenderStyle()
            llm_output = await style_obj.generate(question=data.question)
            self.tokens.input_tokens += style_obj.input_tokens
            self.tokens.output_tokens += style_obj.output_tokens

            add_style = llm_output.get("additional_style", "")
            self._parse_options(column_num, llm_output["chart_type"], add_style, llm_output["scale_type"])
        except Exception as e:
            raise CallError(message=f"图表生成失败：{e!s}", data={"data": data}) from e

        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=RenderOutput(
                output=RenderFormat.model_validate(self._option_template),
            ).model_dump(exclude_none=True, by_alias=True),
        )


    @staticmethod
    def _separate_key_value(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        若数据只有一组（例如：{"aaa": "bbb"}），则分离键值对。

        样例：{"type": "aaa", "value": "bbb"}

        :param data: 待分离的数据
        :return: 分离后的数据
        """
        result = []
        for item in data:
            for key, val in item.items():
                result.append({"type": key, "value": val})
        return result


    def _parse_options(self, column_num: int, chart_style: str, additional_style: str, scale_style: str) -> None:
        """解析LLM做出的图表样式选择"""
        series_template = {}

        if chart_style == "line":
            series_template["type"] = "line"
        elif chart_style == "scatter":
            series_template["type"] = "scatter"
        elif chart_style == "pie":
            column_num = 1
            series_template["type"] = "pie"
            if additional_style == "ring":
                series_template["radius"] = ["40%", "70%"]
        else:
            series_template["type"] = "bar"
            if additional_style == "stacked":
                series_template["stack"] = "total"

        if scale_style == "log":
            self._option_template["yAxis"]["type"] = "log"

        for _ in range(column_num):
            self._option_template["series"].append(series_template)
