# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from apps.llm import get_llm, get_message_model

class ChatSummary:
    def __init__(self):
        raise NotImplementedError("Summary类无法被实例化！")

    @staticmethod
    async def generate_chat_summary(last_summary: str, question: str, answer: str):
        llm = get_llm()
        msg_cls = get_message_model(llm)
        messages = [
            msg_cls(role="system", content="Progressively summarize the lines of conversation provided, adding onto the previous summary."),
            msg_cls(role="user", content=f"{last_summary}\n\nQuestion: {question}\nAnswer: {answer}"),
        ]

        result = llm.invoke(messages)
        return result.content
