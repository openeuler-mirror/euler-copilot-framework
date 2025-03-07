"""问题改写"""
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class QuestionRewrite(CorePattern):
    """问题补全与重写"""

    user_prompt: str = r"""
        <instructions>
          <instruction>
            根据上面的对话，推断用户的实际意图并补全用户的提问内容。
            要求：
              1. 请使用JSON格式输出，参考下面给出的样例；输出不要包含XML标签，不要包含任何解释说明；
              2. 若用户当前提问内容与对话上文不相关，或你认为用户的提问内容已足够完整，请直接输出用户的提问内容。
              3. 补全内容必须精准、恰当，不要编造任何内容。
          </instruction>

          <example>
            <input>openEuler的特点？</input>
            <output>openEuler相较于其他操作系统，其特点是什么？</output>
          </example>
        </instructions>

        <input>
            {question}
        </input>
    """
    """用户提示词"""

    async def generate(self, task_id: str, **kwargs) -> str:  # noqa: ANN003
        """问题补全与重写"""
        question = kwargs["question"]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(question=question)},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk

        return result

