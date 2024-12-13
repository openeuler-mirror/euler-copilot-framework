# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import json
import logging

from apps.llm import get_json_code_block, get_llm, get_message_model


logger = logging.getLogger('gunicorn.error')


class Domain:
    """
    用户领域画像
    """
    def __init__(self):
        raise NotImplementedError("Domain无法被实例化！")

    @staticmethod
    def check_domain(question, answer, domain):
        llm = get_llm()
        prompt = f"""
            请判断以下对话内容涉及领域列表中的哪几个领域

            请按照以下json格式输出:
            ```json
            {{
                "domain":["domain1","domain2","domain3",...] //可能属于一个或者多个领域，必须出现在领域列表中，如果都不涉及可以为空
            }}
            ```

            对话内容:
                提问: {question}
                回答: {answer}

            领域列表:
            {domain}
            """
        output = llm.invoke(prompt)
        logger.info("domain_output: {}".format(output))
        try:
            json_str = get_json_code_block(output.content)
            result = json.loads(json_str)
            return result['domain']
        except Exception as e:
            logger.error(f"检测领域信息出错：{str(e)}")
            return []

    @staticmethod
    def generate_suggestion(summary, last_chat, domain):
        llm = get_llm()
        msg_cls = get_message_model(llm)

        system_prompt = """根据提供的用户领域和历史对话内容，生成三条预测问题，用于指导用户进行下一步的提问。搜索建议必须遵从用户领域，并结合背景信息。
            要求：生成的问题必须为祈使句或疑问句，不得超过30字，生成的问题不要与用户提问完全相同。严格按照以下JSON格式返回：
            ```json
            {{
                "suggestions":["Q:suggestion1","Q:suggestion2","Q:suggestion3"] //返回三条问题
            }}
            ```"""

        user_prompt = """## 背景信息
        {summary}
                
        ## 最近对话
        {last_chat}

        ## 用户领域
        {domain}"""

        messages = [
            msg_cls(role="system", content=system_prompt),
            msg_cls(role="user", content=user_prompt.format(summary=summary, last_chat=last_chat, domain=domain))
        ]
        
        output = llm.invoke(messages)
        print(output)
        try:
            json_str = get_json_code_block(output.content)
            result = json.loads(json_str)
            format_result = []
            for item in result['suggestions']:
                if item.startswith("Q:"):
                    format_result.append({
                        "id": "",
                        "name": "",
                        "question": item[2:]
                    })
                else:
                    format_result.append({
                        "id": "",
                        "name": "",
                        "question": item
                    })
            return format_result
        except Exception as e:
            logger.error(f"生成推荐问题出错：{str(e)}")
            return []
