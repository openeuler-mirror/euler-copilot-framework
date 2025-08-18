# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择图表样式"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.schemas.enum_var import LanguageType

logger = logging.getLogger(__name__)


class RenderStyleResult(BaseModel):
    """选择图表样式结果"""

    chart_type: Literal["bar", "pie", "line", "scatter"] = Field(description="图表类型")
    additional_style: Literal["normal", "stacked", "ring"] | None = Field(description="图表样式")
    scale_type: Literal["linear", "log"] = Field(description="图表比例")


class RenderStyle(CorePattern):
    """选择图表样式"""

    def get_default_prompt(self) -> dict[LanguageType, str]:
        system_prompt = {
            LanguageType.CHINESE: r"""
            你是一个有用的助手。帮助用户在绘制图表时做出样式选择。
            图表标题应简短且少于3个字。
            可用类型：
            - `bar`: 柱状图
            - `pie`: 饼图
            - `line`: 折线图
            - `scatter`: 散点图
            可用柱状图附加样式：
            - `normal`: 普通柱状图
            - `stacked`: 堆叠柱状图
            可用饼图附加样式：
            - `normal`: 普通饼图
            - `ring`: 环形饼图
            可用比例：
            - `linear`: 线性比例
            - `log`: 对数比例
            EXAMPLE
            ## 问题
            查询数据库中的数据，并绘制堆叠柱状图。
            ## 思考
            让我们一步步思考。用户要求绘制堆叠柱状图，因此图表类型应为 `bar`，即柱状图；图表样式
            应为 `stacked`，即堆叠形式。
            ## 答案
            图表类型应为：bar
            图表样式应为：stacked
            比例应为：linear
            END OF EXAMPLE

            让我们开始吧。
            """,
            LanguageType.ENGLISH: r"""
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
        }
        user_prompt = {
            LanguageType.CHINESE: r"""
            ## 问题
            {question}
            ## 思考
            让我们一步步思考。根据用户问题，选择合适的图表类型、样式和比例。
            """,
            LanguageType.ENGLISH: r"""
            ## Question
            {question}

            ## Thought
            Let's think step by step.
            """
        }
        return system_prompt, user_prompt

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化RenderStyle Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """使用LLM选择图表样式"""
        question = kwargs["question"]
        language = kwargs.get("language", LanguageType.CHINESE)
        # 使用Reasoning模型进行推理
        messages = [
            {"role": "system", "content": self.system_prompt[language]},
            {"role": "user", "content": self.user_prompt[language].format(question=question)},
        ]
        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        messages += [
            {"role": "assistant", "content": result},
        ]

        # 使用FunctionLLM模型进行提取参数
        json_gen = JsonGenerator(
            query="根据给定的背景信息，生成预测问题",
            conversation=messages,
            schema=RenderStyleResult.model_json_schema(),
        )
        try:
            result_dict = await json_gen.generate()
            RenderStyleResult.model_validate(result_dict)
        except Exception:
            logger.exception("[RenderStyle] 选择图表样式失败")
            return {}

        return result_dict
