# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""规划生成命令行"""

from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.schemas.enum_var import LanguageType


class InitPlan(CorePattern):
    """规划生成命令行"""

    def get_default_prompt(self) -> dict[LanguageType, str]:
        system_prompt = {
            LanguageType.CHINESE: r"""
            你是一个计划生成器。对于给定的目标，**制定一个简单的计划**，该计划可以逐步生成合适的命令行参数和标志。

            你会收到一个"命令前缀"，这是已经确定和生成的命令部分。你需要基于这个前缀使用标志和参数来完成命令。

            在每一步中，指明使用哪个外部工具以及工具输入来获取证据。

            工具可以是以下之一：
            (1) Option["指令"]：查询最相似的命令行标志。只接受一个输入参数，"指令"必须是搜索字符串。搜索字符串应该详细且包含必要的数据。
            (2) Argument[名称]<值>：将任务中的数据放置到命令行的特定位置。接受两个输入参数。

            所有步骤必须以"Plan: "开头，且少于150个单词。
            不要添加任何多余的步骤。
            确保每个步骤都包含所需的所有信息 - 不要跳过步骤。
            不要在证据后面添加任何额外数据。

            开始示例

            任务：在后台运行一个新的alpine:latest容器，将主机/root文件夹挂载至/data，并执行top命令。
            前缀：`docker run`
            用法：`docker run ${OPTS} ${image} ${command}`。这是一个Python模板字符串。OPTS是所有标志的占位符。参数必须是 \
            ["image", "command"] 其中之一。
            前缀描述：二进制程序`docker`的描述为"Docker容器平台"，`run`子命令的描述为"从镜像创建并运行一个新的容器"。

            Plan: 我需要一个标志使容器在后台运行。 #E1 = Option[在后台运行单个容器]
            Plan: 我需要一个标志，将主机/root目录挂载至容器内/data目录。 #E2 = Option[挂载主机/root目录至/data目录]
            Plan: 我需要从任务中解析出镜像名称。 #E3 = Argument[image]<alpine:latest>
            Plan: 我需要指定容器中运行的命令。 #E4 = Argument[command]<top>
            Final: 组装上述线索，生成最终命令。 #F

            示例结束

            让我们开始！
        """,
            LanguageType.ENGLISH: r"""
            You are a plan generator. For a given goal, **draft a simple plan** that can step-by-step generate the \
            appropriate command line arguments and flags.

            You will receive a "command prefix", which is the already determined and generated command part. You need to \
            use the flags and arguments based on this prefix to complete the command.

            In each step, specify which external tool to use and the tool input to get the evidence.

            The tool can be one of the following:
            (1) Option["instruction"]: Query the most similar command line flag. Only accepts one input parameter, \
            "instruction" must be a search string. The search string should be detailed and contain necessary data.
            (2) Argument["name"]<value>: Place the data from the task into a specific position in the command line. \
            Accepts two input parameters.

            All steps must start with "Plan: " and be less than 150 words.
            Do not add any extra steps.
            Ensure each step contains all the required information - do not skip steps.
            Do not add any extra data after the evidence.

            Start example

            Task: Run a new alpine:latest container in the background, mount the host /root folder to /data, and execute \
            the top command.
            Prefix: `docker run`
            Usage: `docker run ${OPTS} ${image} ${command}`. This is a Python template string. OPTS is a placeholder for all \
            flags. The arguments must be one of ["image", "command"].
            Prefix description: The description of binary program `docker` is "Docker container platform", and the \
            description of `run` subcommand is "Create and run a new container from an image".

            Plan: I need a flag to make the container run in the background. #E1 = Option[Run a single container in the \
            background]
            Plan: I need a flag to mount the host /root directory to /data directory in the container. #E2 = Option[Mount \
            host /root directory to /data directory]
            Plan: I need to parse the image name from the task. #E3 = Argument[image]<alpine:latest>
            Plan: I need to specify the command to be run in the container. #E4 = Argument[command]<top>
            Final: Assemble the above clues to generate the final command. #F

            End example
            
            Let's get started!
        """,
        }
        """系统提示词"""

        user_prompt = {
            LanguageType.CHINESE: r"""
            任务：{instruction}
            前缀：`{binary_name} {subcmd_name}`
            用法：`{subcmd_usage}`。这是一个Python模板字符串。OPTS是所有标志的占位符。参数必须是 {argument_list} 其中之一。
            前缀描述：二进制程序`{binary_name}`的描述为"{binary_description}"，`{subcmd_name}`子命令的描述为\
            "{subcmd_description}"。

            请生成相应的计划。
        """,
            LanguageType.ENGLISH: r"""
            Task: {instruction}
            Prefix: `{binary_name} {subcmd_name}`
            Usage: `{subcmd_usage}`. This is a Python template string. OPTS is a placeholder for all flags. The arguments \
            must be one of {argument_list}.
            Prefix description: The description of binary program `{binary_name}` is "{binary_description}", and the \
            description of `{subcmd_name}` subcommand is "{subcmd_description}".

            Please generate the corresponding plan.
        """,
        }
        """用户提示词"""
        return system_prompt, user_prompt

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """处理Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """生成命令行evidence"""
        spec = kwargs["spec"]
        binary_name = kwargs["binary_name"]
        subcmd_name = kwargs["subcmd_name"]
        language = kwargs.get("language", LanguageType.CHINESE)
        binary_description = spec[binary_name][0]
        subcmd_usage = spec[binary_name][2][subcmd_name][1]
        subcmd_description = spec[binary_name][2][subcmd_name][0]

        argument_list = []
        for key in spec[binary_name][2][subcmd_name][3]:
            argument_list += [key]

        messages = [
            {"role": "system", "content": self.system_prompt[language]},
            {
                "role": "user",
                "content": self.user_prompt[language].format(
                    instruction=kwargs["instruction"],
                    binary_name=binary_name,
                    subcmd_name=subcmd_name,
                    binary_description=binary_description,
                    subcmd_description=subcmd_description,
                    subcmd_usage=subcmd_usage,
                    argument_list=argument_list,
                ),
            },
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result


class PlanEvaluator(CorePattern):
    """计划评估器"""

    def get_default_prompt(self) -> dict[LanguageType, str]:
        system_prompt = {
            LanguageType.CHINESE: r"""
            你是一个计划评估器。你的任务是评估给定的计划是否合理和完整。

            一个好的计划应该：
            1. 涵盖原始任务的所有要求
            2. 使用适当的工具收集必要的信息
            3. 具有清晰和逻辑的步骤
            4. 没有冗余或不必要的步骤

            对于计划中的每个步骤，评估：
            1. 工具选择是否适当
            2. 输入参数是否清晰和充分
            3. 该步骤是否有助于实现最终目标

            请回复：
            "VALID" - 如果计划良好且完整
            "INVALID: <原因>" - 如果计划有问题，请解释原因
        """,
            LanguageType.ENGLISH: r"""
            You are a plan evaluator. Your task is to evaluate whether the given plan is reasonable and complete.

            A good plan should:
            1. Cover all requirements of the original task
            2. Use appropriate tools to collect necessary information
            3. Have clear and logical steps
            4. Have no redundant or unnecessary steps

            For each step in the plan, evaluate:
            1. Whether the tool selection is appropriate
            2. Whether the input parameters are clear and sufficient
            3. Whether this step helps achieve the final goal

            Please reply:
            "VALID" - If the plan is good and complete
            "INVALID: <原因>" - If the plan has problems, please explain the reason
        """,
        }
        """系统提示词"""

        user_prompt = {
            LanguageType.CHINESE: r"""
            任务：{instruction}
            计划：{plan}

            评估计划并回复"VALID"或"INVALID: <原因>"。
        """,
            LanguageType.ENGLISH: r"""
            Task: {instruction}
            Plan: {plan}

            Evaluate the plan and reply with "VALID" or "INVALID: <原因>".
        """,
        }
        """用户提示词"""
        return system_prompt, user_prompt

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:
        """生成计划评估结果"""
        language = kwargs.get("language", LanguageType.CHINESE)
        messages = [
            {"role": "system", "content": self.system_prompt[language]},
            {
                "role": "user",
                "content": self.user_prompt[language].format(
                    instruction=kwargs["instruction"],
                    plan=kwargs["plan"],
                ),
            },
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result


class RePlanner(CorePattern):
    """重新规划器"""

    def get_default_prompt(self) -> dict[LanguageType, str]:
        system_prompt = {
            LanguageType.CHINESE: r"""
            你是一个计划重新规划器。当计划被评估为无效时，你需要生成一个新的、改进的计划。

            新计划应该：
            1. 解决评估中提到的所有问题
            2. 保持与原始计划相同的格式
            3. 更加精确和完整
            4. 为每个步骤使用适当的工具

            遵循与原始计划相同的格式：
            - 每个步骤应以"Plan: "开头
            - 包含带有适当参数的工具使用
            - 保持步骤简洁和重点突出
            - 以"Final"步骤结束
        """,
            LanguageType.ENGLISH: r"""
            You are a plan replanner. When the plan is evaluated as invalid, you need to generate a new, improved plan.

            The new plan should:
            1. Solve all problems mentioned in the evaluation
            2. Keep the same format as the original plan
            3. Be more precise and complete
            4. Use appropriate tools for each step

            Follow the same format as the original plan:
            - Each step should start with "Plan: "
            - Include tool usage with appropriate parameters
            - Keep steps concise and focused
            - End with the "Final" step
        """,
        }
        """系统提示词"""

        user_prompt = {
            LanguageType.CHINESE: r"""
            任务：{instruction}
            原始计划：{plan}
            评估：{evaluation}

            生成一个新的、改进的计划，解决评估中提到的所有问题。
        """,
            LanguageType.ENGLISH: r"""
            Task: {instruction}
            Original Plan: {plan}
            Evaluation: {evaluation}

            Generate a new, improved plan that solves all problems mentioned in the evaluation.
        """,
        }
        """用户提示词"""
        return system_prompt, user_prompt

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:
        """生成重新规划结果"""
        language = kwargs.get("language", LanguageType.CHINESE)
        messages = [
            {"role": "system", "content": self.system_prompt[language]},
            {
                "role": "user",
                "content": self.user_prompt[language].format(
                    instruction=kwargs["instruction"],
                    plan=kwargs["plan"],
                    evaluation=kwargs["evaluation"],
                ),
            },
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result
