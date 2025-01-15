"""JSON参数生成Prompt

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from copy import deepcopy
from typing import Any, Optional

from apps.common.config import config
from apps.constants import LOGGER
from apps.llm.function import FunctionLLM
from apps.llm.patterns.core import CorePattern


class Json(CorePattern):
    """使用FunctionCall范式，生成JSON参数"""

    system_prompt: str = r"""
        Extract parameter data from conversations using given JSON Schema definitions.
        Conversations tags: "<conversation>" and "</conversation>".
        Schema tags: "<tool_call>" and "</tool_call>".
        The output must be valid JSON without any additional formatting or comments.

        Example:
        {"search_key": "杭州"}

        Requirements:
        1. Use "null" if no valid values are present, e.g., `{"search_key": null}`.
        2. Do not fabricate parameters.
        3. Example values are for format reference only.
        4. No comments or instructions in the output JSON.

        EXAMPLE
        <conversation>
        [HUMAN] 创建“任务1”，并进行扫描
        </conversation>

        <tool_call>
        {
          "type": "object",
          "properties": {
            "name": {
                "type": "string",
                "description": "扫描任务的名称",
                "example": "Task 1"
            },
            "enable": {
                "type": "boolean",
                "description": "是否启用该任务",
                "pattern": "(true|false)"
            }
          },
          "required": ["name", "enable"]
        }
        </tool_call>

        Output:
        {"scan": [{"name": "Task 1", "enable": true}]}
        END OF EXAMPLE
    """
    """系统提示词"""

    user_prompt: str = r"""
        <conversation>
        {conversation}
        </conversation>

        <tool_call>
        {slot_schema}
        </tool_call>

        Output:
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Json模式"""
        super().__init__(system_prompt, user_prompt)


    @staticmethod
    def _remove_null_params(input_val: Any) -> Any:  # noqa: ANN401
        """递归地移除输入数据中的空值参数。

        :param input_val: 输入的数据，可以是字典、列表或其他类型。
        :return: 移除空值参数后的数据。
        """
        if isinstance(input_val, dict):
            new_dict = {}
            for key, value in input_val.items():
                nested = Json._remove_null_params(value)
                if isinstance(nested, (bool, int, float)) or nested:
                    new_dict[key] = nested
            return new_dict
        if isinstance(input_val, list):
            new_list = []
            for v in input_val:
                cleaned_v = Json._remove_null_params(v)
                if cleaned_v:
                    new_list.append(cleaned_v)
            if len(new_list) > 0:
                return new_list
            return None
        return input_val


    @staticmethod
    def _unstrict_spec(spec: dict[str, Any]) -> dict[str, Any]:  # noqa: C901, PLR0912
        """移除spec中的required属性"""
        # 设置必要字段
        new_spec = {}
        new_spec["type"] = spec.get("type", "string")
        new_spec["description"] = spec.get("description", "")

        # 处理对象和数组两种递归情况
        if "items" in spec:
            new_spec["items"] = Json._unstrict_spec(spec["items"])
        if "properties" in spec:
            new_spec["properties"] = {}
            for key in spec["properties"]:
                new_spec["properties"][key] = Json._unstrict_spec(spec["properties"][key])

        # 把必要信息放到描述中，起提示作用
        if "pattern" in spec:
            new_spec["description"] += f"\nThe regex pattern is: {spec['pattern']}."
        if "example" in spec:
            new_spec["description"] += f"\nFor example: {spec['example']}."
        if "default" in spec:
            new_spec["description"] += f"\nThe default value is: {spec['default']}."
        if "enum" in spec:
            new_spec["description"] += f"\nValue must be one of: {', '.join(str(item) for item in spec['enum'])}."
        if "minimum" in spec:
            new_spec["description"] += f"\nValue must be greater than or equal to: {spec['minimum']}."
        if "maximum" in spec:
            new_spec["description"] += f"\nValue must be less than or equal to: {spec['maximum']}."
        if "minLength" in spec:
            new_spec["description"] += f"\nValue must be at least {spec['minLength']} characters long."
        if "maxLength" in spec:
            new_spec["description"] += f"\nValue must be at most {spec['maxLength']} characters long."
        if "minItems" in spec:
            new_spec["description"] += f"\nArray must contain at least {spec['minItems']} items."
        if "maxItems" in spec:
            new_spec["description"] += f"\nArray must contain at most {spec['maxItems']} items."

        return new_spec


    async def generate(self, _task_id: str, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """调用大模型，生成JSON参数"""
        spec: dict[str, Any] = kwargs["spec"]
        strict = kwargs.get("strict", True)
        if not strict:
            spec = deepcopy(spec)
            spec = Json._unstrict_spec(spec)

        # 转换对话记录
        conversation_str = ""
        for item in kwargs["conversation"]:
            if item["role"] == "user":
                conversation_str += f"[HUMAN] {item['content']}"
            if item["role"] == "assistant":
                conversation_str += f"[ASSISTANT] {item['content']}"
            if item["role"] == "tool":
                conversation_str += f"[TOOL OUTPUT] {item['content']}"

        user_input = self.user_prompt.format(conversation=conversation_str, slot_schema=spec)

        # 使用FunctionLLM进行提参
        messages_list = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        # 尝试FunctionCall
        result = await FunctionLLM().call(
            messages=messages_list,
            schema=spec,
            max_tokens=config["SCHEDULER_MAX_TOKENS"],
            temperature=config["SCHEDULER_TEMPERATURE"],
        )

        try:
            LOGGER.info(f"[Json] FunctionCall Result：{result}")
            result = json.loads(result)
        except json.JSONDecodeError as e:
            err = "JSON解析失败"
            raise ValueError(err) from e

        # 移除空值参数
        return Json._remove_null_params(result)
