from typing import Any
import json
from jsonschema import validate
import logging
from apps.llm.function import JsonGenerator
from apps.llm.reasoning import ReasoningLLM

logger = logging.getLogger(__name__)


class MCPBase:
    """MCP基类"""

    @staticmethod
    async def get_resoning_result(prompt: str, resoning_llm: ReasoningLLM = ReasoningLLM()) -> str:
        """获取推理结果"""
        # 调用推理大模型
        message = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Please provide a JSON response based on the above information and schema."},
        ]
        result = ""
        async for chunk in resoning_llm.call(
            message,
            streaming=False,
            temperature=0.07,
            result_only=False,
        ):
            result += chunk

        return result

    @staticmethod
    async def _parse_result(result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        json_result = await JsonGenerator._parse_result_by_stack(result, schema)
        if json_result is not None:
            return json_result
        json_generator = JsonGenerator(
            "Please provide a JSON response based on the above information and schema.\n\n",
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": result},
            ],
            schema,
        )
        json_result = await json_generator.generate()
        return json_result
