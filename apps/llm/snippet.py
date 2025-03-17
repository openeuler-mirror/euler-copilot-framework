"""上下文转提示词"""


def convert_context_to_prompt(context: list[dict[str, str]]) -> str:
    """上下文转提示词"""
    prompt = "<conversation>\n"
    for item in context:
        prompt += f"<{item['role']}>\n{item['content']}\n</{item['role']}>\n"
    prompt += "</conversation>\n"
    return prompt


def facts_to_prompt(facts: list[str]) -> str:
    """事实转提示词"""
    prompt = "<facts>\n"
    for item in facts:
        prompt += f"- {item}\n"
    prompt += "</facts>\n"
    return prompt


def history_questions_to_prompt(history_questions: list[str]) -> str:
    """历史问题转提示词"""
    prompt = "<history_list>\n"
    for item in history_questions:
        prompt += f"<question>{item}</question>\n"
    prompt += "</history_list>\n"
    return prompt


def choice_to_prompt(choices: list[dict[str, Any]]) -> str:
    """选项转提示词"""
    prompt = "<options>\n"
    for item in choices:
        prompt += f"<item><name>{item['name']}</name><description>{item['description']}</description></item>\n"
    prompt += "</options>\n"
    return prompt
