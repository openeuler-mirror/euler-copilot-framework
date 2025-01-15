"""规划生成命令行

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import Optional

from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class InitPlan(CorePattern):
    """规划生成命令行"""

    system_prompt: str = r"""
        You are a plan generator. For the given objective, **make a simple plan** that can generate \
        proper commandline arguments and flags step by step.

        You will be given a "command prefix", which is the part of the command that has been determined and generated. \
        You need to complete the command based on this prefix using flags and arguments.

        In each step, indicate which external tool together with tool input to retrieve evidences.

        Tools can be one of the following:
        (1) Option["directive"]: Query the most similar command-line flag. Takes only one input parameter, \
        and "directive" must be the search string. The search string should be in detail and contain essential data.
        (2) Argument[name]<value>: Place the data in the task to a specific position in the command-line. \
        Takes exactly two input parameters.

        All steps must begin with "Plan: ", and less than 150 words.
        Do not add any superfluous steps.
        Make sure that each step has all the information needed - do not skip steps.
        Do not add any extra data behind the evidence.

        BEGIN EXAMPLE

        Task: 在后台运行一个新的alpine:latest容器，将主机/root文件夹挂载至/data，并执行top命令。
        Prefix: `docker run`
        Usage: `docker run ${OPTS} ${image} ${command}`. 这是一个Python模板字符串。OPTS是所有标志的占位符。参数必须是 \
        ["image", "command"] 其中之一。
        Prefix Description: 二进制程序`docker`的描述为“Docker容器平台”，`run`子命令的描述为“从镜像创建并运行一个新的容器”。

        Plan: 我需要一个标志使容器在后台运行。 #E1 = Option[在后台运行单个容器]
        Plan: 我需要一个标志，将主机/root目录挂载至容器内/data目录。 #E2 = Option[挂载主机/root目录至/data目录]
        Plan: 我需要从任务中解析出镜像名称。 #E3 = Argument[image]<alpine:latest>
        Plan: 我需要指定容器中运行的命令。 #E4 = Argument[command]<top>
        Final: 组装上述线索，生成最终命令。 #F

        END OF EXAMPLE

        Let's Begin!
    """
    """系统提示词"""

    user_prompt: str = r"""
        Task: {instruction}
        Prefix: `{binary_name} {subcmd_name}`
        Usage: `{subcmd_usage}`. 这是一个Python模板字符串。OPTS是所有标志的占位符。参数必须是 {argument_list} 其中之一。
        Prefix Description: 二进制程序`{binary_name}`的描述为“{binary_description}”，`{subcmd_name}`子命令的描述为\
        “{subcmd_description}”。

        Generate your plan accordingly.
    """
    """用户提示词"""

    def __init__(self, system_prompt: Optional[str] = None, user_prompt: Optional[str] = None) -> None:
        """处理Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """生成命令行evidence"""
        spec = kwargs["spec"]
        binary_name = kwargs["binary_name"]
        subcmd_name = kwargs["subcmd_name"]
        binary_description = spec[binary_name][0]
        subcmd_usage = spec[binary_name][2][subcmd_name][1]
        subcmd_description = spec[binary_name][2][subcmd_name][0]
        task_id = kwargs["task_id"]

        argument_list = []
        for key in spec[binary_name][2][subcmd_name][3]:
            argument_list += [key]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                instruction=kwargs["instruction"],
                binary_name=binary_name,
                subcmd_name=subcmd_name,
                binary_description=binary_description,
                subcmd_description=subcmd_description,
                subcmd_usage=subcmd_usage,
                argument_list=argument_list,
            )},
        ]

        result = ""
        async for chunk in ReasoningLLM().call(task_id, messages, streaming=False):
            result += chunk

        return result


# class PlanEvaluator:
#     system_prompt = """You are a plan evaluator. Your task is: for the given user objective and your original plan, \
#
#
#     """
#     user_prompt = """"""
#
#     def __init__(self, system_prompt: Union[str, None] = None, user_prompt: Union[str, None] = None):
#         if system_prompt is not None:
#             self.system_prompt = system_prompt
#         if user_prompt is not None:
#             self.user_prompt = user_prompt
#
#     @staticmethod
#     @sglang.function
#     def _plan(s):
#         pass
#
#     def generate(self, **kwargs) -> str:
#         pass

