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
    async def _parse_result_by_stack(result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        left_index = result.find('{')
        right_index = result.rfind('}')
        if left_index != -1 and right_index != -1 and left_index < right_index:
            try:
                tmp_js = json.loads(result[left_index:right_index + 1])
                validate(instance=tmp_js, schema=schema)
                return tmp_js
            except Exception as e:
                logger.error("[McpBase] 解析结果失败: %s", e)
        stack = []
        json_candidates = []
        # 定义括号匹配关系
        bracket_map = {')': '(', ']': '[', '}': '{'}

        for i, char in enumerate(result):
            # 遇到左括号则入栈
            if char in bracket_map.values():
                stack.append((char, i))
            # 遇到右括号且栈不为空时检查匹配
            elif char in bracket_map.keys() and stack:
                if not stack:
                    continue
                top_char, top_index = stack[-1]
                # 检查是否匹配当前右括号
                if top_char == bracket_map[char]:
                    stack.pop()
                    # 当栈为空且当前是右花括号时，认为找到一个完整JSON
                    if not stack and char == '}':
                        json_str = result[top_index:i+1]
                        json_candidates.append(json_str)
                else:
                    # 如果不匹配，清空栈
                    stack.clear()
        # 移除重复项并保持顺序
        seen = set()
        unique_jsons = []
        for json_str in json_candidates[::]:
            if json_str not in seen:
                seen.add(json_str)
                unique_jsons.append(json_str)

        for json_str in unique_jsons:
            try:
                tmp_js = json.loads(json_str)
                validate(instance=tmp_js, schema=schema)
                return tmp_js
            except Exception as e:
                logger.error("[McpBase] 解析结果失败: %s", e)
        return None

    @staticmethod
    async def _parse_result(result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        json_result = await MCPBase._parse_result_by_stack(result, schema)
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
