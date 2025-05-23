"""问题改写"""

from typing import Any, ClassVar

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json_gen import Json
from apps.llm.reasoning import ReasoningLLM


class QuestionRewrite(CorePattern):
    """问题补全与重写"""

    system_prompt: str = r"""You are a helpful assistant."""
    """系统提示词"""
    user_prompt: str = r"""
        <instructions>
          <instruction>
            根据上面的对话，推断用户的实际意图并补全用户的提问内容。
            要求：
              1. 请使用JSON格式输出，参考下面给出的样例；不要包含任何XML标签，不要包含任何解释说明；
              2. 若用户当前提问内容与对话上文不相关，或你认为用户的提问内容已足够完整，请直接输出用户的提问内容。
              3. 补全内容必须精准、恰当，不要编造任何内容。

              输出格式样例：
              {{
                "question": "补全后的问题"
              }}
          </instruction>

          <example>
            <input>openEuler的特点？</input>
            <output>
              {{
                "question": "openEuler相较于其他操作系统，其特点是什么？"
              }}
            </output>
          </example>
        </instructions>

        <input>{question}</input>
        <output>
    """
    """用户提示词"""

    slot_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "补全后的问题",
            },
        },
        "required": ["question"],
    }
    """最终输出的JSON Schema"""

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """问题补全与重写"""
        question = kwargs["question"]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(question=question)},
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        messages += [{"role": "assistant", "content": result}]
        question_dict = await Json().generate(conversation=messages, spec=self.slot_schema)

        if not question_dict or "question" not in question_dict or not question_dict["question"]:
            return question
        return question_dict["question"]
