# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# Agent调度器

from __future__ import annotations

import json
from typing import List

from apps.scheduler.executor import FlowExecuteExecutor
from apps.scheduler.pool.pool import Pool
from apps.scheduler.utils import Select, Recommend
from apps.llm import get_llm, get_message_model


MAX_RECOMMEND = 3


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    目前，Scheduler只会构造并执行1个Flow。后续可以改造为Router，用于连接多个Executor（Multi-Agent）
    """

    # 上下文
    context: str = ""
    # 用户原始问题
    question: str

    def __init__(self):
        raise NotImplementedError("Scheduler无法被实例化！")

    @staticmethod
    async def choose_flow(question: str, user_selected_plugins: List[str]) -> str | None:
        """
        依据用户的输入和选择，构造对应的Flow。

        - 当用户没有选择任何Plugin时，直接进行智能问答
        - 当用户选择Plugin时，挑选最适合的Flow

        :param question: 用户输入（用户问题）
        :param user_selected_plugins: 用户选择的插件，可以一次选择多个
        :result: 经LLM选择的Flow Name
        """

        # 用户什么都不选，直接智能问答
        if len(user_selected_plugins) == 0:
            return None

        # 自动识别：选择TopK插件
        elif len(user_selected_plugins) == 1 and user_selected_plugins[0] == "auto":
            # 用户要求自动识别
            plugin_top = Pool().get_k_plugins(question)
            # 聚合插件的Flow
            plugin_top_list = []
            for plugin in plugin_top:
                plugin_top_list.append(plugin.name)

        else:
            # 用户指定了插件
            plugin_top_list = user_selected_plugins

        flows = Pool().get_k_flows(question, plugin_top_list, 2)

        # 使用大模型选择Top1
        flow_list = []
        for item in flows:
            flow_list.append({
                "name": item.plugin + "." + item.name,
                "description": item.description
            })
        if len(user_selected_plugins) == 1 and user_selected_plugins[0] == "auto":
            # 用户选择自动识别时，包含智能问答
            flow_list.append({
                "name": "KnowledgeBase",
                "description": "回答上述工具无法直接进行解决的用户问题。"
            })
        top_flow = await Select().top_flow(choice=flow_list, instruction=question)

        if top_flow == "KnowledgeBase":
            return None
        # 返回流的ID
        return top_flow

    @staticmethod
    async def run_certain_flow(context: str, question: str, user_selected_flow: str, session_id: str, files: List[str] | None):
        """
        构造FlowExecutor，并执行所选择的流

        :param context: 上下文信息
        :param question: 用户输入（用户问题）
        :param user_selected_flow: 用户所选择的Flow的Name
        :param session_id: 当前用户的登录Session。目前用于部分插件鉴权，后续将用于Flow与用户交互过程中的暂停与恢复。
        :param files: 用户上传的文件的ID（暂未使用，后续配合LogGPT上传文件分析等需要文件的功能）
        """
        flow_exec = FlowExecuteExecutor(params={
            "name": user_selected_flow,
            "question": question,
            "context": context,
            "files": files,
            "session_id": session_id
        })

        response = {
            "message": "",
            "output": {}
        }
        async for chunk in flow_exec.run():
            if "data" in chunk[:6]:
                yield "data: " + json.dumps({"content": chunk[6:]}, ensure_ascii=False) + "\n\n"
            else:
                response = json.loads(chunk[7:])

        # 返回自然语言结果和结构化数据结果
        llm = get_llm()
        msg_cls = get_message_model(llm)
        messages = [
            msg_cls(role="system", content="详细回答用户的问题，保留一切必要信息。工具输出中包含的Markdown代码段、Markdown表格等内容必须原封不动输出。"),
            msg_cls(role="user", content=f"""## 用户问题
{question}

## 工具描述
{flow_exec.description}

## 工具输出
{response}""")
        ]
        async for chunk in llm.astream(messages):
            yield "data: " + json.dumps({"content": chunk.content}, ensure_ascii=False) + "\n\n"

        # 提取出最终的结构化信息
        # 样例：{"type": "api", "data": "API返回值原始数据（string）"}
        structured_data = {
            "type": response["output"]["type"],
            "data": response["output"]["data"]["output"],
        }
        yield "data: " + json.dumps(structured_data, ensure_ascii=False) + "\n\n"

    @staticmethod
    async def plan_next_flow(summary: str, current_flow_name: str | None, user_selected_plugins: List[str], question: str):
        """
        生成用户“下一步”Flow的推荐。

        - 若Flow的配置文件中已定义`next_flow[]`字段，则直接使用该字段给定的值
        - 否则，使用LLM进行选择。将根据用户的插件选择情况限定范围

        选择“下一步”Flow后，根据当前Flow的执行结果和“下一步”Flow的描述，生成改写的或预测的问题。

        :param summary: 上下文总结，包含当前Flow的执行结果。
        :param current_flow_name: 当前执行的Flow的Name，用于避免重复选择同一个Flow
        :param user_selected_plugins: 用户选择的插件列表，用于限定推荐范围
        :param question: 用户当前Flow的问题输入
        :return: 列表，包含“下一步”Flow的Name和预测问题
        """
        if current_flow_name is not None:
            # 是否有预定义的Flow关系？有就直接展示这些关系
            next_flow_data = []
            plugin_name, flow_name = current_flow_name.split(".")
            _, current_flow_data = Pool().get_flow(flow_name, plugin_name)
            predefined_next_flow_name = current_flow_data.next_flow

            if predefined_next_flow_name is not None:
                result_num = 0
                # 最多只能有3个推荐Flow
                for current_flow in predefined_next_flow_name:
                    result_num += 1
                    if result_num > MAX_RECOMMEND:
                        break
                    # 从Pool中查找该Flow
                    flow_metadata, _ = Pool().get_flow(current_flow, plugin_name)
                    # 根据该Flow对应的Description，改写问题
                    rewrite_question = await Recommend().recommend(action_description=flow_metadata.description, background=summary)
                    # 将改写后的问题与Flow名字的对应关系关联起来
                    plugin_metadata = Pool().get_plugin(plugin_name)
                    next_flow_data.append({
                        "id": plugin_name + "." + current_flow,
                        "name": plugin_metadata.show_name,
                        "question": rewrite_question
                    })

                    # 返回改写后的问题
                    return next_flow_data

        # 没有预定义的Flow，走一次choose_flow
        if len(user_selected_plugins) == 1 and user_selected_plugins[0] == "auto":
            plugin_top = Pool().get_k_plugins(question)
            user_selected_plugins = []
            for plugin in plugin_top:
                user_selected_plugins.append(plugin.name)

        next_flow_data = []
        result = Pool().get_k_flows(question, user_selected_plugins)
        for current_flow in result:
            if current_flow.name == current_flow_name:
                continue

            flow_metadata, _ = Pool().get_flow(current_flow.name, current_flow.plugin)
            rewrite_question = await Recommend().recommend(action_description=flow_metadata.description, background=summary)
            plugin_metadata = Pool().get_plugin(current_flow.plugin)
            next_flow_data.append({
                "id": current_flow.plugin + "." + current_flow.name,
                "name": plugin_metadata.show_name,
                "question": rewrite_question
            })

        return next_flow_data
