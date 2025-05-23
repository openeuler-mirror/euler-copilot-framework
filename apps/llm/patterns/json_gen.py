"""
JSON参数生成Prompt

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
from copy import deepcopy
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.config import Config
from apps.llm.function import FunctionLLM
from apps.llm.patterns.core import CorePattern

logger = logging.getLogger(__name__)


class Json(CorePattern):
    """使用FunctionCall范式，生成JSON参数"""

    system_prompt: str = r"""You are a helpful assistant that can call functions."""
    """系统提示词"""
    user_prompt: str = r"""
        <instructions>
          <instruction>
            你是一个可以调用工具函数的智能助手。目前你正在使用工具函数，但是函数缺少必要的参数。
            你需要根据对话内容和JSON Schema定义，提取信息并填充符合要求的JSON参数。
            要求：
            1. 输出必须是有效的JSON格式，不包含任何注释或额外格式。
            2. 如果找不到有效值，直接使用null作为值。
            3. 不要编造参数，不要编造参数的值。
            4. 示例值仅作为格式参考，不要直接输出示例值。
          </instruction>

          <example>
            <conversation>
              <user>创建"任务1"，并进行扫描</user>
            </conversation>

            <schema>
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
            </schema>

            <output>
              {"scan": [{"name": "Task 1", "enable": true}]}
            </output>
          </example>
        </instructions>

        <conversation>
        {{ conversation }}
        </conversation>

        <schema>
        {{ slot_schema }}
        </schema>

        <output>
    """
    """用户提示词"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化Json模式"""
        super().__init__(system_prompt, user_prompt)


    @staticmethod
    def _remove_null_params(input_val: Any) -> Any:
        """
        递归地移除输入数据中的空值参数。

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
            new_spec["description"] += f"\n正则表达式模式为：{spec['pattern']}"
        if "example" in spec:
            new_spec["description"] += f"\n示例：{spec['example']}"
        if "default" in spec:
            new_spec["description"] += f"\n默认值为：{spec['default']}"
        if "enum" in spec:
            new_spec["description"] += f"\n取值必须是以下之一：{', '.join(str(item) for item in spec['enum'])}"
        if "minimum" in spec:
            new_spec["description"] += f"\n值必须大于或等于：{spec['minimum']}"
        if "maximum" in spec:
            new_spec["description"] += f"\n值必须小于或等于：{spec['maximum']}"
        if "minLength" in spec:
            new_spec["description"] += f"\n长度必须至少为 {spec['minLength']} 个字符"
        if "maxLength" in spec:
            new_spec["description"] += f"\n长度不能超过 {spec['maxLength']} 个字符"
        if "minItems" in spec:
            new_spec["description"] += f"\n数组至少包含 {spec['minItems']} 个项目"
        if "maxItems" in spec:
            new_spec["description"] += f"\n数组最多包含 {spec['maxItems']} 个项目"

        return new_spec


    async def generate(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
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
                conversation_str += f"<user>{item['content']}</user>"
            if item["role"] == "assistant":
                conversation_str += f"<assistant>{item['content']}</assistant>"
            if item["role"] == "tool":
                conversation_str += f"<tool>{item['content']}</tool>"

        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        user_input = env.from_string(self.user_prompt).render(
            conversation=conversation_str,
            slot_schema=spec,
        )

        # 使用FunctionLLM进行提参
        messages_list = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        # 尝试FunctionCall
        result = await FunctionLLM().call(
            messages=messages_list,
            schema=spec,
            max_tokens=Config().get_config().llm.max_tokens,
            temperature=Config().get_config().llm.temperature,
        )

        try:
            logger.info("[Json] FunctionCall 结果: %s", result)
            result = json.loads(result)
        except json.JSONDecodeError as e:
            err = "JSON解析失败"
            raise ValueError(err) from e

        # 移除空值参数
        return Json._remove_null_params(result)
