"""事实提取"""
from typing import Any, ClassVar, Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json_gen import Json
from apps.llm.reasoning import ReasoningLLM


class Facts(CorePattern):
    """事实提取"""

    system_prompt: str = ""
    """系统提示词（暂不使用）"""

    user_prompt: str = r"""
        <instructions>
            <instruction>
                从对话中提取关键信息，并将它们组织成独一无二的、易于理解的事实，包含用户偏好、关系、实体等有用信息。
                以下是需要关注的信息类型以及有关如何处理输入数据的详细说明。

                **你需要关注的信息类型**
                1. 实体：对话中涉及到的实体。例如：姓名、地点、组织、事件等。
                2. 偏好：对待实体的态度。例如喜欢、讨厌等。
                3. 关系：用户与实体之间，或两个实体之间的关系。例如包含、并列、互斥等。
                4. 动作：对实体产生影响的具体动作。例如查询、搜索、浏览、点击等。

                **要求**
                1. 事实必须准确，只能从对话中提取。不要将样例中的信息体现在输出中。
                2. 事实必须清晰、简洁、易于理解。必须少于30个字。
                3. 必须按照以下JSON格式输出：

                {{
                    "facts": ["事实1", "事实2", "事实3"]
                }}
            </instruction>

            <example>
                <conversation>
                    <user>杭州西湖有哪些景点？</user>
                    <assistant>杭州西湖是中国浙江省杭州市的一个著名景点，以其美丽的自然风光和丰富的文化遗产而闻名。西湖周围有许多著名的景点，包括著名的苏堤、白堤、断桥、三潭印月等。西湖以其清澈的湖水和周围的山脉而著名，是中国最著名的湖泊之一。</assistant>
                </conversation>

                <output>
                    {{
                        "facts": ["杭州西湖有苏堤、白堤、断桥、三潭印月等景点"]
                    }}
                </output>
            </example>
        </instructions>

        {conversation}
        <output>
    """
    """用户提示词"""

    slot_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "description": "The facts extracted from the conversation.",
                "items": {
                    "type": "string",
                    "description": "A fact string.",
                },
            },
        },
        "required": ["facts"],
    }
    """最终输出的JSON Schema"""


    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)


    async def generate(self, task_id: str, **kwargs) -> list[str]:  # noqa: ANN003
        """事实提取"""
        conversation = "<conversation><user>" + kwargs["message"]["question"] + "</user><assistant>" + kwargs["message"]["answer"] + "</assistant></conversation>"
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(conversation=conversation)},
        ]
        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk

        messages += [{"role": "assistant", "content": result}]
        fact_dict = await Json().generate("", conversation=messages, spec=self.slot_schema)

        if not fact_dict or "facts" not in fact_dict or not fact_dict["facts"]:
            return []
        return fact_dict["facts"]
