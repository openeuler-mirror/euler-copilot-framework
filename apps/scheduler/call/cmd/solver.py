"""命令行解析器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import copy
import re
from typing import Any

from apps.llm.patterns.json_gen import Json
from apps.scheduler.call.cmd.assembler import CommandlineAssembler


class Solver:
    """解析命令行生成器"""

    @staticmethod
    async def _get_option(agent_input: str, collection_name: str, binary_name: str, subcmd_name: str, spec: dict[str, Any]) -> tuple[str, str]:
        """选择最匹配的命令行参数"""
        # 选择最匹配的Global Options
        global_options = CommandlineAssembler.get_data("global_option", agent_input, collection_name, binary_name, num=2)
        # 选择最匹配的Options
        options = CommandlineAssembler.get_data("option", agent_input, collection_name, binary_name, subcmd_name, 3)
        # 判断哪个更符合标准
        choices = options + global_options
        result, result_desc = await CommandlineAssembler.select_option(agent_input, choices)

        option_type = ""
        # 从BTDL里面拿出JSON Schema
        if not option_type:
            for opt in global_options:
                if result == opt["name"]:
                    option_type = "global_option"
                    break
        if not option_type:
            for opt in options:
                if result == opt["name"]:
                    option_type = "option"
                    break

        if option_type == "global_option":
            spec = spec[binary_name][1][result]
        elif option_type == "option":
            spec = spec[binary_name][2][subcmd_name][2][result]
        else:
            err = "No option found."
            raise ValueError(err)

        # 返回参数名字、描述
        return result, spec, result_desc

    @staticmethod
    async def _get_value(question: str, description: str, spec: dict[str, Any]) -> dict[str, Any]:
        """根据用户目标和JSON Schema，生成命令行参数"""
        gen_input = f"""
        用户的目标为： [[{question}]]

        依照JSON Schema，生成下列参数：
        {description}

        严格按照JSON Schema格式输出，不要添加或编造字段。""".format(objective=question, description=description)
        return await Json().generate("", question=gen_input, background="Empty.", spec=spec)


    @staticmethod
    async def process_output(output: str, question: str, collection_name: str, binary_name: str, subcmd_name: str, spec: dict[str, Any]) -> tuple[str, str]:  # noqa: PLR0913
        """对规划器输出的evidence进行解析，生成命令行参数"""
        spec_template = {
            "type": "object",
            "properties": {},
        }
        opt_spec = copy.deepcopy(spec_template)
        full_opt_desc = ""
        arg_spec = copy.deepcopy(spec_template)
        full_arg_desc = ""

        lines = output.split("\n")
        for line in lines:
            if not line.startswith("Plan:"):
                continue

            evidence = re.search(r"#E.*", line)
            if not evidence:
                continue
            evidence = evidence.group(0)

            if "Option" in evidence:
                action_input = re.search(r"\[.*\]", evidence)
                if not action_input:
                    continue
                action_input = action_input.group(0)
                action_input = action_input.rstrip("]").lstrip("[")
                opt_name, single_opt_spec, opt_desc = await Solver._get_option(action_input, collection_name, binary_name, subcmd_name, spec)

                opt_spec["properties"].update({opt_name: single_opt_spec})
                full_opt_desc += f"- {opt_name}: {opt_desc}\n"

            elif "Argument" in evidence:
                name = re.search(r"\[.*\]", evidence)
                if not name:
                    continue
                name = name.group(0)
                name = name.rstrip("]").lstrip("[")
                name = name.lower()

                if name not in spec[binary_name][2][subcmd_name][3]:
                    continue

                value = re.search(r"<.*>", evidence)
                if not value:
                    continue
                value = value.group(0)
                value = value.rstrip(">").lstrip("<")

                arg_spec["properties"].update({name: spec[binary_name][2][subcmd_name][3][name]})
                arg_desc = spec[binary_name][2][subcmd_name][3][name]["description"]
                full_arg_desc += f"- {name}: {arg_desc}. 可能的值： {value}.\n"

        result_dict = {
            "opts": {},
            "args": {},
        }
        result_dict["opts"].update(await Solver._get_value(question, full_opt_desc, opt_spec))
        result_dict["args"].update(await Solver._get_value(question, full_arg_desc, arg_spec))

        result_cmd = CommandlineAssembler.convert_dict_to_cmdline(result_dict, spec[binary_name][2][subcmd_name][1])
        full_description = "各命令行标志的描述为：\n" + full_opt_desc + "\n\n各参数的描述为：\n" + full_arg_desc
        return result_cmd, full_description
