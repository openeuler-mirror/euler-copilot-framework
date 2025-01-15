"""Render Call: 选择图表样式

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Any, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json import Json
from apps.llm.reasoning import ReasoningLLM


class RenderStyle(CorePattern):
    """选择图表样式"""

    @property
    def predefined_system_prompt(self) -> str:
        """系统提示词"""
        return r"""
            You are a helpful assistant. Help the user make style choices when drawing a chart.
            Chart title should be short and less than 3 words.

            Available types:
            - `bar`: Bar graph
            - `pie`: Pie graph
            - `line`: Line graph
            - `scatter`: Scatter graph

            Available bar additional styles:
            - `normal`: Normal bar graph
            - `stacked`: Stacked bar graph

            Available pie additional styles:
            - `normal`: Normal pie graph
            - `ring`: Ring pie graph

            Available scales:
            - `linear`: Linear scale
            - `log`: Logarithmic scale

            EXAMPLE
            ## Question
            查询数据库中的数据，并绘制堆叠柱状图。

            ## Thought
            Let's think step by step. The user requires drawing a stacked bar chart, so the chart type should be `bar`, \
            i.e. a bar chart; the chart style should be `stacked`, i.e. a stacked form.

            ## Answer
            The chart type should be: bar
            The chart style should be: stacked
            The scale should be: linear

            END OF EXAMPLE

            Let's begin.
        """

    def predefined_user_prompt(self) -> str:
        """用户提示词"""
        return r"""
            ## Question
            {question}

            ## Thought
            Let's think step by step.
        """

    def slot_schema(self) -> dict[str, Any]:
        """槽位Schema"""
        return {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "description": "The type of the chart.",
                    "enum": ["bar", "pie", "line", "scatter"],
                },
                "additional_style": {
                    "type": "string",
                    "description": "The additional style of the chart.",
                    "enum": ["normal", "stacked", "ring"],
                },
                "scale_type": {
                    "type": "string",
                    "description": "The scale of the chart.",
                    "enum": ["linear", "log"],
                },
            },
            "required": ["chart_type", "scale_type"],
        }

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化RenderStyle Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, task_id: str, **kwargs) -> dict[str, Any]:
        """使用LLM选择图表样式"""
        question = kwargs["question"]

        # 使用Reasoning模型进行推理
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": self._user_prompt.format(question=question)},
        ]
        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk

        messages += [
            {"role": "assistant", "content": result},
        ]

        # 使用FunctionLLM模型进行提取参数
        return await Json().generate(task_id, conversation=messages, spec=self.slot_schema)
