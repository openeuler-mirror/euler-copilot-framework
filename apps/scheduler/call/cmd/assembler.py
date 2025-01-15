"""BTDL：命令行组装器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import string
from typing import Any, Literal, Optional

from apps.llm.patterns.select import Select
from apps.scheduler.vector import DocumentWrapper, VectorDB


class CommandlineAssembler:
    """命令行组装器"""

    @staticmethod
    def convert_dict_to_cmdline(args_dict: dict[str, Any], usage: str) -> str:
        """将字典转换为命令行"""
        opts_result = ""
        for key, val in args_dict["opts"].items():
            if isinstance(val, bool) and val:
                opts_result += f" {key}"
                continue

            opts_result += f" {key} {val}"
        # opts_result = opts_result.lstrip(" ") + " ${OPTS}"
        opts_result = opts_result.lstrip(" ")

        result = string.Template(usage)
        return result.safe_substitute(OPTS=opts_result, **args_dict["args"])

    @staticmethod
    def get_command(instruction: str, collection_name: str) -> str:
        """获取命令行"""
        collection = VectorDB.get_collection(collection_name)
        return VectorDB.get_docs(collection, instruction, {"type": "binary"}, 1)[0].metadata["name"]

    @staticmethod
    def _documents_to_choices(docs: list[DocumentWrapper]) -> list[dict[str, Any]]:
        return [{
            "name": doc.metadata["name"],
            "description": doc.data,
        } for doc in docs]

    @staticmethod
    def get_data(
        query_type: Literal["subcommand", "global_option", "option", "argument"],
        instruction: str, collection_name: str, binary_name: str, subcmd_name: Optional[str] = None, num: int = 5,
    ) -> list[dict[str, Any]]:
        collection = VectorDB.get_collection(collection_name)
        if collection is None:
            err = f"Collection {collection_name} not found"
            raise ValueError(err)

        # Query certain type
        requirements = {
            "$and": [
                {"type": query_type},
                {"binary": binary_name},
            ],
        }
        if subcmd_name is not None:
            requirements["$and"].append({"subcmd": subcmd_name})

        result_list = VectorDB.get_docs(collection, instruction, requirements, num)

        return CommandlineAssembler._documents_to_choices(result_list)

    @staticmethod
    async def select_option(instruction: str, choices: list[dict[str, Any]]) -> tuple[str, str]:
        """选择当前最合适的命令行选项"""
        top_option = await Select().generate(choices, instruction=instruction)
        top_option_description = [choice["description"] for choice in choices if choice["name"] == top_option]
        return top_option, top_option_description[0]
