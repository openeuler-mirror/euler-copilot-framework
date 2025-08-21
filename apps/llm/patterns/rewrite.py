# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题改写"""

import logging

from pydantic import BaseModel, Field
from textwrap import dedent

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.llm.token import TokenCalculator
from apps.schemas.enum_var import LanguageType
logger = logging.getLogger(__name__)


class QuestionRewriteResult(BaseModel):
    """问题补全与重写结果"""

    question: str = Field(description="补全后的问题")


_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


class QuestionRewrite(CorePattern):
    """问题补全与重写"""

    def get_default_prompt(self) -> dict[LanguageType, str]:
        system_prompt = {
            LanguageType.CHINESE: dedent(r"""
          <instructions>
            <instruction>
              根据历史对话，推断用户的实际意图并补全用户的提问内容,历史对话被包含在<history>标签中，用户意图被包含在<question>标签中。
              要求：
                1. 请使用JSON格式输出，参考下面给出的样例；不要包含任何XML标签，不要包含任何解释说明；
                2. 若用户当前提问内容与对话上文不相关，或你认为用户的提问内容已足够完整，请直接输出用户的提问内容。
                3. 补全内容必须精准、恰当，不要编造任何内容。
                4. 请输出补全后的问题，不要输出其他内容。
                输出格式样例：
                ```json
                {
                  "question": "补全后的问题"
                }
                ```
            </instruction>

            <example>
              <history>
                <qa>
                  <question>
                    openEuler的特点是什么？
                  </question>
                  <answer>
                    openEuler相较于其他操作系统，其特点是支持多种硬件架构，并且提供稳定、安全、高效的操作系统平台。
                  </answer>
                </qa>
                <qa>
                  <question>
                    openEuler的优势有哪些？
                  </question>
                  <answer>
                    openEuler的优势包括开源、社区支持、以及对云计算和边缘计算的优化。
                  </answer>
                </qa>
              </history>

              <question>
                详细点？
              </question>
              <output>
              ```json
                {
                  "question": "openEuler的特点是什么？请详细说明其优势和应用场景。"
                }
              ```
              </output>
            </example>
          </instructions>
          <history>
            {{history}}
          </history>
          <question>
            {{question}}
          </question>
      """),
            LanguageType.ENGLISH: dedent(r"""
          <instructions>
            <instruction>
              Based on the historical dialogue, infer the user's actual intent and complete the user's question. The historical dialogue is contained within the <history> tags, and the user's intent is contained within the <question> tags.
              Requirements:
                1. Please output in JSON format, referring to the example provided below; do not include any XML tags or any explanatory notes;
                2. If the user's current question is unrelated to the previous dialogue or you believe the user's question is already complete enough, directly output the user's question.
                3. The completed content must be precise and appropriate; do not fabricate any content.
                4. Output only the completed question; do not include any other content.
                Example output format:
                ```json
                {
                  "question": "The completed question"
                }
                ```
            </instruction>

            <example>
              <history>
                <qa>
                  <question>
                    What are the features of openEuler?
                  </question>
                  <answer>
                    Compared to other operating systems, openEuler's features include support for multiple hardware architectures and providing a stable, secure, and efficient operating system platform.
                  </answer>
                </qa>
                <qa>
                  <question>
                    What are the advantages of openEuler?
                  </question>
                  <answer>
                    The advantages of openEuler include being open-source, having community support, and optimizations for cloud and edge computing.
                  </answer>
                </qa>
              </history>

              <question>
                More details?
              </question>
              <output>
              ```json
                {
                  "question":  "What are the features of openEuler? Please elaborate on its advantages and application scenarios."
                }
              </output>
            </example>
          </instructions>
          <history>
            {{history}}
          </history>
          <question>
            {{question}}
          </question>
      """)
        }

        """用户提示词"""
        user_prompt = {
            LanguageType.CHINESE: r"""
        <instructions>
          请输出补全后的问题
        </instructions>
      """,
            LanguageType.ENGLISH: r"""
        <instructions>
          Please output the completed question
        </instructions>
      """}
        return system_prompt, user_prompt

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """问题补全与重写"""
        history = kwargs.get("history", [])
        question = kwargs["question"]
        llm = kwargs.get("llm", None)
        language = kwargs.get("language", LanguageType.CHINESE)
        if not llm:
            llm = ReasoningLLM()
        leave_tokens = llm._config.max_tokens
        leave_tokens -= TokenCalculator().calculate_token_length(
            messages=[{"role": "system", "content": _env.from_string(self.system_prompt[language]).render(
                history="", question=question)},
                {"role": "user", "content": _env.from_string(self.user_prompt[language]).render()}])
        if leave_tokens <= 0:
            logger.error("[QuestionRewrite] 大模型上下文窗口不足，无法进行问题补全与重写")
            return question
        index = 0
        qa = ""
        while index < len(history)-1 and leave_tokens > 0:
            q = history[index-1].get("content", "")
            a = history[index].get("content", "")
            sub_qa = f"<qa>\n<question>\n{q}\n</question>\n<answer>\n{a}\n</answer>\n</qa>"
            leave_tokens -= TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "user", "content": sub_qa}
                ],
                pure_text=True
            )
            if leave_tokens >= 0:
                qa = sub_qa + qa
            index += 2
        messages = [{"role": "system", "content": _env.from_string(self.system_prompt[language]).render(
            history=qa, question=question)}, {"role": "user", "content": _env.from_string(self.user_prompt[language]).render()}]
        result = ""
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens
        tmp_js = await JsonGenerator._parse_result_by_stack(result, QuestionRewriteResult.model_json_schema())
        if tmp_js is not None:
            return tmp_js['question']
        messages += [{"role": "assistant", "content": result}]
        json_gen = JsonGenerator(
            query="根据给定的背景信息，生成预测问题",
            conversation=messages,
            schema=QuestionRewriteResult.model_json_schema(),
        )
        try:
            question_dict = QuestionRewriteResult.model_validate(await json_gen.generate())
        except Exception:
            logger.exception("[QuestionRewrite] 问题补全与重写失败")
            return question

        return question_dict.question
