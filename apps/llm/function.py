# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于FunctionCall的大模型"""

import json
import logging
import re
from textwrap import dedent
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from jsonschema import Draft7Validator

from jsonschema import validate
from apps.common.config import Config
from apps.constants import JSON_GEN_MAX_TRIAL, REASONING_END_TOKEN
from apps.llm.prompt import JSON_GEN_BASIC
from apps.llm.adapters import AdapterFactory, get_provider_from_endpoint

# 导入异常处理相关模块
import openai
import httpx
from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError

logger = logging.getLogger(__name__)


class FunctionLLM:
    """用于FunctionCall的模型"""

    def __init__(self, llm_config=None) -> None:
        """
        初始化用于FunctionCall的模型

        目前支持：
        - vllm
        - ollama
        - function_call
        - json_mode
        - structured_output
        
        :param llm_config: 可选的LLM配置，如果不提供则使用配置文件中的function_call配置
        """
        # 使用传入的配置或从配置文件获取
        if llm_config:
            self._config = llm_config
            # 如果没有backend字段，根据模型特性推断
            if not hasattr(self._config, 'backend'):
                # 默认使用json_mode，这对大多数模型都适用
                class ConfigWithBackend:
                    def __init__(self, base_config):
                        self.model = base_config.model
                        self.endpoint = base_config.endpoint
                        self.api_key = getattr(base_config, 'key', getattr(base_config, 'api_key', ''))
                        self.max_tokens = getattr(base_config, 'max_tokens', 8192)
                        self.temperature = getattr(base_config, 'temperature', 0.7)
                        self.backend = "json_mode"  # 默认使用json_mode
                
                self._config = ConfigWithBackend(llm_config)
        else:
            # 暂存config；这里可以替代为从其他位置获取
            self._config = Config().get_config().function_call
            
        if not self._config.model:
            err_msg = "[FunctionCall] 未设置FuntionCall所用模型！"
            logger.error(err_msg)
            raise ValueError(err_msg)

        # 初始化适配器
        self._provider = get_provider_from_endpoint(self._config.endpoint)
        self._adapter = AdapterFactory.create_adapter(self._provider, self._config.model)
        
        self._params = {
            "model": self._config.model,
            "messages": [],
            "extra_body": {}
        }
        if self._config.backend != "ollama":
            self._params["timeout"] = 300
        if self._config.backend == "ollama":
            import ollama

            if not self._config.api_key:
                self._client = ollama.AsyncClient(host=self._config.endpoint)
            else:
                self._client = ollama.AsyncClient(
                    host=self._config.endpoint,
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                    },
                )

        else:
            import openai

            if not self._config.api_key:
                self._client = openai.AsyncOpenAI(
                    base_url=self._config.endpoint)
            else:
                self._client = openai.AsyncOpenAI(
                    base_url=self._config.endpoint,
                    api_key=self._config.api_key,
                )

    async def _call_openai(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
        enable_thinking: bool = False,
    ) -> str:
        """
        调用openai模型生成JSON

        :param list[dict[str, str]] messages: 历史消息列表
        :param dict[str, Any] schema: 输出JSON Schema
        :param int | None max_tokens: 最大Token长度
        :param float | None temperature: 大模型温度
        :param bool enable_thinking: 是否启用思维链
        :return: 生成的JSON
        :rtype: str
        """
        self._params.update({
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })

        # 🔑 特殊处理：如果provider是siliconflow，强制使用json_mode
        if self._provider == "siliconflow":
            logger.info("[FunctionCall] 检测到SiliconFlow provider，启用JSON模式")
            # 确保系统消息中包含JSON输出提示
            if messages and messages[0]["role"] == "system":
                if "JSON" not in messages[0]["content"]:
                    messages[0]["content"] += "\nYou are a helpful assistant designed to output JSON."
            self._params["response_format"] = {"type": "json_object"}
            
        elif self._config.backend == "vllm":
            self._params["extra_body"] = {"guided_json": schema}

        elif self._config.backend == "json_mode":
            logger.warning("[FunctionCall] json_mode无法确保输出格式符合要求，使用效果将受到影响")
            self._params["response_format"] = {"type": "json_object"}

        elif self._config.backend == "structured_output":
            self._params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "generate",
                    "description": "Generate answer based on the background information",
                    "schema": schema,
                    "strict": True,
                },
            }

        elif self._config.backend == "function_call":
            logger.warning("[FunctionCall] function_call无法确保一定调用工具，使用效果将受到影响")
            self._params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "generate",
                        "description": "Generate answer based on the background information",
                        "parameters": schema,
                    },
                },
            ]

        # 使用适配器调整参数，对于JSON生成任务禁用thinking以避免解析问题
        adapted_params = self._adapter.adapt_create_params(self._params, enable_thinking=False)
        
        try:
            # type: ignore[arg-type]
            response = await self._client.chat.completions.create(**adapted_params)
        except AuthenticationError as e:
            logger.error("[FunctionCall] API认证失败: %s", e)
            raise ValueError(f"API认证失败，请检查API密钥: {e}")
        except RateLimitError as e:
            logger.error("[FunctionCall] API调用频率限制: %s", e)
            raise ValueError(f"API调用频率超限，请稍后重试: {e}")
        except APIConnectionError as e:
            logger.error("[FunctionCall] API连接失败: %s", e)
            raise ValueError(f"无法连接到API服务: {e}")
        except APITimeoutError as e:
            logger.error("[FunctionCall] API请求超时: %s", e)
            raise ValueError(f"API请求超时，请稍后重试: {e}")
        except APIError as e:
            logger.error("[FunctionCall] API调用错误: %s", e)
            # 检查是否是账户欠费问题
            if hasattr(e, 'code') and e.code == 'Arrearage':
                raise ValueError("账户余额不足，请充值后重试")
            elif hasattr(e, 'status_code') and e.status_code == 400:
                raise ValueError(f"API请求参数错误: {e}")
            else:
                raise ValueError(f"API调用失败: {e}")
        except httpx.ConnectTimeout:
            logger.error("[FunctionCall] 网络连接超时")
            raise ValueError("网络连接超时，请检查网络连接")
        except httpx.ReadTimeout:
            logger.error("[FunctionCall] 网络读取超时")
            raise ValueError("网络读取超时，请稍后重试")
        except Exception as e:
            logger.error("[FunctionCall] 未知错误: %s", e)
            raise ValueError(f"LLM调用发生未知错误: {e}")

        try:
            # 尝试获取function call结果
            if (response.choices and
                response.choices[0].message.tool_calls and
                    response.choices[0].message.tool_calls[0].function.arguments):
                logger.info("[FunctionCall] 大模型输出：%s",
                            response.choices[0].message.tool_calls[0].function.arguments)
                return response.choices[0].message.tool_calls[0].function.arguments
        except (AttributeError, IndexError, TypeError) as e:
            logger.warning(
                "[FunctionCall] 无法获取function call结果，尝试解析content: %s", e)

        # 如果无法获取function call结果，尝试解析content
        try:
            if response.choices and response.choices[0].message.content:
                ans = response.choices[0].message.content
                logger.info("[FunctionCall] 大模型输出：%s", ans)
                return await FunctionLLM.process_response(ans)
            else:
                logger.error("[FunctionCall] 大模型返回空响应")
                raise ValueError("大模型返回空响应")
        except Exception as e:
            logger.error("[FunctionCall] 处理响应失败: %s", e)
            raise ValueError(f"处理大模型响应失败: {e}")

    @staticmethod
    async def process_response(response: str) -> str:
        """处理大模型的输出"""
        # 去掉推理过程，避免干扰
        for token in REASONING_END_TOKEN:
            response = response.split(token)[-1]

        # 尝试解析JSON
        response = dedent(response).strip()
        error_flag = False
        try:
            json.loads(response)
        except Exception:  # noqa: BLE001
            error_flag = True

        if not error_flag:
            return response

        # 尝试提取```json中的JSON
        logger.warning("[FunctionCall] 直接解析失败！尝试提取```json中的JSON")
        try:
            json_str = re.findall(r"```json(.*)```", response, re.DOTALL)[-1]
            json_str = dedent(json_str).strip()
            json.loads(json_str)
        except Exception:  # noqa: BLE001
            # 尝试直接通过括号匹配JSON
            logger.warning("[FunctionCall] 提取失败！尝试正则提取JSON")
            try:
                json_str = re.findall(r"\{.*\}", response, re.DOTALL)[-1]
                json_str = dedent(json_str).strip()
                json.loads(json_str)
            except Exception:  # noqa: BLE001
                json_str = "{}"

        return json_str

    async def _call_ollama(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        调用ollama模型生成JSON

        :param list[dict[str, str]] messages: 历史消息列表
        :param dict[str, Any] schema: 输出JSON Schema
        :param int | None max_tokens: 最大Token长度
        :param float | None temperature: 大模型温度
        :return: 生成的对话回复
        :rtype: str
        """
        self._params.update({
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "format": schema,
        })

        try:
            # type: ignore[arg-type]
            response = await self._client.chat(**self._params)
        except Exception as e:
            logger.error("[FunctionCall] Ollama调用失败: %s", e)
            raise ValueError(f"Ollama调用失败: {e}")

        try:
            content = response.message.content or ""
            if not content.strip():
                logger.error("[FunctionCall] Ollama返回空内容")
                raise ValueError("Ollama返回空内容")
            return await self.process_response(content)
        except Exception as e:
            logger.error("[FunctionCall] 处理Ollama响应失败: %s", e)
            raise ValueError(f"处理Ollama响应失败: {e}")

    async def call(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        调用FunctionCall小模型

        不开放流式输出
        """
        # 检查max_tokens和temperature是否设置
        if max_tokens is None:
            max_tokens = self._config.max_tokens
        if temperature is None:
            temperature = self._config.temperature

        try:
            if self._config.backend == "ollama":
                json_str = await self._call_ollama(messages, schema, max_tokens, temperature)
            elif self._config.backend in ["function_call", "json_mode", "response_format", "vllm", "structured_output"]:
                json_str = await self._call_openai(messages, schema, max_tokens, temperature)
            else:
                err = f"未知的Function模型后端: {self._config.backend}"
                logger.error("[FunctionCall] %s", err)
                raise ValueError(err)
        except ValueError:
            # 重新抛出已知的ValueError
            raise
        except Exception as e:
            logger.error("[FunctionCall] 调用模型失败: %s", e)
            raise ValueError(f"调用模型失败: {e}")

        # 解析JSON响应
        if not json_str or not json_str.strip():
            logger.error("[FunctionCall] 模型返回空字符串")
            raise ValueError("模型返回空响应")

        try:
            result = json.loads(json_str)
            if not isinstance(result, dict):
                logger.warning("[FunctionCall] 模型返回非字典类型: %s", type(result))
                return {}
            return result
        except json.JSONDecodeError as e:
            logger.error("[FunctionCall] JSON解析失败：%s, 原始内容: %s",
                         e, json_str[:200])
            raise ValueError(f"模型返回的内容不是有效的JSON格式: {e}")
        except Exception as e:
            logger.error("[FunctionCall] 处理JSON响应失败: %s", e)
            raise ValueError(f"处理模型响应失败: {e}")


class JsonGenerator:
    """JSON生成器"""
    @staticmethod
    async def _parse_result_by_stack(result: str, schema: dict[str, Any]) -> str:
        """解析推理结果"""
        # 首先尝试解析对象格式
        left_index = result.find('{')
        right_index = result.rfind('}')
        if left_index != -1 and right_index != -1 and left_index < right_index:
            try:
                tmp_js = json.loads(result[left_index:right_index + 1])
                validate(instance=tmp_js, schema=schema)
                return tmp_js
            except Exception as e:
                logger.error("[JsonGenerator] 对象格式解析失败: %s", e)

        # 如果对象格式失败，尝试解析数组格式并取第一个元素
        array_left = result.find('[')
        array_right = result.rfind(']')
        if array_left != -1 and array_right != -1 and array_left < array_right:
            try:
                array_result = json.loads(result[array_left:array_right + 1])
                if isinstance(array_result, list) and len(array_result) > 0:
                    # 取数组的第一个元素
                    first_item = array_result[0]
                    validate(instance=first_item, schema=schema)
                    logger.info("[JsonGenerator] 从数组中提取第一个元素作为结果")
                    return first_item
            except Exception as e:
                logger.error("[JsonGenerator] 数组格式解析失败: %s", e)
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
                logger.error("[JsonGenerator] 解析结果失败: %s", e)
        return None

    def __init__(self, query: str, conversation: list[dict[str, str]], schema: dict[str, Any]) -> None:
        """初始化JSON生成器"""
        self._query = query
        self._conversation = conversation
        self._schema = schema

        self._trial = {}
        self._count = 0
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._err_info = ""

    async def _assemble_message(self) -> str:
        """组装消息"""
        # 检查类型
        function_call = Config().get_config().function_call.backend == "function_call"

        # 渲染模板
        template = self._env.from_string(JSON_GEN_BASIC)
        return template.render(
            query=self._query,
            conversation=self._conversation,
            previous_trial=self._trial,
            schema=self._schema,
            function_call=function_call,
            err_info=self._err_info,
        )

    async def _single_trial(self, max_tokens: int | None = None, temperature: float | None = None) -> dict[str, Any]:
        """单次尝试"""
        prompt = await self._assemble_message()
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "please generate a JSON response based on the above information and schema./no_think"},
        ]
        function = FunctionLLM()
        return await function.call(messages, self._schema, max_tokens, temperature)

    async def generate(self) -> dict[str, Any]:
        """生成JSON"""
        try:
            Draft7Validator.check_schema(self._schema)
        except Exception as e:
            logger.error("[JSONGenerator] Schema验证失败: %s", e)
            raise ValueError(f"JSON Schema无效: {e}")

        validator = Draft7Validator(self._schema)
        logger.info("[JSONGenerator] Schema：%s", self._schema)

        last_error = None
        while self._count < JSON_GEN_MAX_TRIAL:
            self._count += 1
            try:
                result = await self._single_trial()
                if not result:
                    logger.warning("[JSONGenerator] 第%d次尝试返回空结果", self._count)
                    last_error = "模型返回空结果"
                    continue

                # 验证结果是否符合schema
                validator.validate(result)
                logger.info("[JSONGenerator] 第%d次尝试成功生成有效JSON", self._count)
                return result

            except ValueError as e:
                # 这是来自FunctionLLM的错误，直接抛出
                logger.error(
                    "[JSONGenerator] 第%d次尝试失败，LLM调用错误: %s", self._count, e)
                raise e
            except Exception as err:
                err_info = str(err)
                err_info = err_info.split("\n\n")[0]
                self._err_info = err_info
                last_error = err_info
                logger.warning(
                    "[JSONGenerator] 第%d次尝试失败，Schema验证错误: %s", self._count, err_info)
                continue

        # 所有尝试都失败了
        error_msg = f"经过{JSON_GEN_MAX_TRIAL}次尝试仍无法生成有效JSON"
        if last_error:
            error_msg += f"，最后一次错误: {last_error}"
        logger.error("[JSONGenerator] %s", error_msg)
        raise ValueError(error_msg)
