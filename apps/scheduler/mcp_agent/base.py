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
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in resoning_llm.call(
            message,
            streaming=False,
            temperature=0.07,
            result_only=True,
        ):
            result += chunk

        return result

    @staticmethod
    async def _parse_result(result: str, schema: dict[str, Any], left_str: str = '{', right_str: str = '}') -> str:
        """解析推理结果"""
        left_index = result.find(left_str)
        right_index = result.rfind(right_str)
        flag = True
        if left_str == -1 or right_str == -1:
            flag = False

        if left_index > right_index:
            flag = False
        if flag:
            try:
                tmp_js = json.loads(result[left_index:right_index + 1])
                validate(instance=tmp_js, schema=schema)
            except Exception as e:
                logger.error("[McpBase] 解析结果失败: %s", e)
                flag = False
        if not flag:
            json_generator = JsonGenerator(
                "请提取下面内容中的json\n\n",
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "请提取下面内容中的json\n\n"+result},
                ],
                schema,
            )
            json_result = await json_generator.generate()
        else:
            json_result = json.loads(result[left_index:right_index + 1])
        return json_result
