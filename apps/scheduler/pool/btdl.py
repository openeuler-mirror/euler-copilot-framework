import hashlib
from typing import Any, Union

import yaml
from chromadb import Collection

from apps.scheduler.vector import DocumentWrapper, VectorDB

btdl_spec = []


"""
基本的载入形态：

{"docker": ("描述", [{全局options}], {"cmd1名字": ("cmd1描述", "cmd1用法", [{cmd1选项}], [{cmd1参数}], "cmd1例子")})}
"""
class BTDLLoader:
    """二进制描述文件 加载器"""

    vec_collection: Collection

    def __init__(self, collection_name: str) -> None:
        """初始化BTDL加载器"""
        # Create or use existing vec_db
        self.vec_collection = VectorDB.get_collection(collection_name)

    @staticmethod
    # 循环检查每一个参数，确定为合法JSON Schema
    def _check_single_argument(argument: dict[str, Any], *, strict: bool = True) -> None:
        """检查单个参数的JSON Schema是否正确"""
        if strict and "name" not in argument:
            err = "argument must have a name"
            raise ValueError(err)
        if strict and "description" not in argument:
            err = f"argument {argument['name']} must have a description"
            raise ValueError(err)
        if "type" not in argument:
            err = f"argument {argument['name']} must have a type"
            raise ValueError(err)
        if argument["type"] not in ["string", "integer", "number", "boolean", "array", "object"]:
            err = f"argument {argument['name']} type not supported"
            raise ValueError(err)
        if argument["type"] == "array":
            if "items" not in argument:
                err = f"argument {argument['name']}: array type must have items"
                raise ValueError(err)
            BTDLLoader._check_single_argument(argument["items"], strict=False)
        if argument["type"] == "object":
            if "properties" not in argument:
                err = f"argument {argument['name']}: object type must have properties"
                raise ValueError(err)
            for value in argument["properties"].values():
                BTDLLoader._check_single_argument(value, strict=False)

    def _load_single_subcmd(self, binary_name: str, subcmd_spec: dict[str, Any]) -> dict[str, tuple[str, str, dict[str, Any], dict[str, Any], str]]:
        if "name" not in subcmd_spec:
            err = "subcommand must have a name"
            raise ValueError(err)
        name = subcmd_spec["name"]

        if "description" not in subcmd_spec:
            err = f"subcommand {name} must have a description"
            raise ValueError(err)
        description = subcmd_spec["description"]

        if "usage" not in subcmd_spec:
            # OPTS和ARGS算保留字
            usage = "{OPTS} {ARGS}"
        else:
            if not isinstance(subcmd_spec["usage"], str):
                err = f"subcommand {name}: usage must be a string"
                raise ValueError(err)
            usage = subcmd_spec["usage"]

        options = {}
        option_docs = []
        if "options" in subcmd_spec:
            if not isinstance(subcmd_spec["options"], list):
                err = f"subcommand {name}: options must be a list"
                raise ValueError(err)

            for item in subcmd_spec["options"]:
                BTDLLoader._check_single_argument(item)

                new_item = item
                if "required" not in item:
                    new_item.update({"required": False})

                option_name = new_item["name"]
                new_item.pop("name")
                options.update({option_name: new_item})

                id = hashlib.md5(f"o_{binary_name}_sub_{name}_{option_name}".encode()).hexdigest()
                option_docs.append(DocumentWrapper(
                    id=id,
                    data=new_item["description"],
                    metadata={
                        "binary": binary_name,
                        "subcmd": name,
                        "type": "option",
                        "name": option_name,
                    },
                ))

            VectorDB.add_docs(self.vec_collection, option_docs)

        arguments = {}
        arguments_docs = []
        if "arguments" in subcmd_spec:
            if not isinstance(subcmd_spec["arguments"], list):
                err = f"subcommand {name}: arguments must be a list"
                raise ValueError(err)

            for item in subcmd_spec["arguments"]:
                BTDLLoader._check_single_argument(item)

                new_item = item
                if "required" not in item:
                    new_item.update({"required": False})
                if "multiple" not in item:
                    new_item.update({"multiple": False})

                argument_name = new_item["name"]
                new_item.pop("name")
                arguments.update({argument_name: new_item})

                id = hashlib.md5(f"a_{binary_name}_sub_{name}_{argument_name}".encode()).hexdigest()
                arguments_docs.append(DocumentWrapper(
                    id=id,
                    data=new_item["description"],
                    metadata={
                        "binary": binary_name,
                        "subcmd": name,
                        "type": "argument",
                        "name": argument_name,
                    },
                ))

            VectorDB.add_docs(self.vec_collection, arguments_docs)

        if "examples" in subcmd_spec:
            if not isinstance(subcmd_spec["examples"], list):
                err = f"subcommand {name}: examples must be a list"
                raise ValueError(err)

            examples = "以下是几组命令行，以及它的作用的示例：\n"
            for items in subcmd_spec["examples"]:
                examples += "`{}`: {}\n".format(items["command"], items["description"])
        else:
            examples = ""

        # 组装结果
        return {name: (description, usage, options, arguments, examples)}

    def _load_global_options(self, binary_name: str, cmd_spec: dict[str, Any]) -> dict[str, Any]:
        if "global_options" not in cmd_spec:
            return {}

        if not isinstance(cmd_spec["global_options"], list):
            err = "global_options must be a list"
            raise TypeError(err)

        result = {}
        result_doc = []
        for item in cmd_spec["global_options"]:
            try:
                BTDLLoader._check_single_argument(item)

                new_item = item
                if "required" not in item:
                    new_item.update({"required": False})
                name = new_item["name"]
                new_item.pop("name")
                result.update({name: new_item})

                id = hashlib.md5(f"g_{binary_name}_{name}".encode()).hexdigest()
                result_doc.append(DocumentWrapper(
                    id=id,
                    data=new_item["description"],
                    metadata={
                        "binary": binary_name,
                        "type": "global_option",
                        "name": name,
                    },
                ))
            except ValueError as e:  # noqa: PERF203
                err = f"Value error in global_options: {e!s}"
                raise ValueError(err) from e

        VectorDB.add_docs(self.vec_collection, result_doc)
        return result

    def load_btdl(self, filename: str) -> dict[str, Any]:
        # Load single btdl.yaml
        try:
            yaml_data = yaml.safe_load(open(filename, "r", encoding="utf-8"))
        except FileNotFoundError as e:
            err = "BTDLLoader: file not found."
            raise FileNotFoundError(err) from e

        result = {}
        result_doc = []
        for item in yaml_data["cmd"]:
            # 依序处理每一个命令
            key = item["name"]
            description = item["description"]

            cmd_spec = yaml_data[item["name"]]
            global_options = self._load_global_options(key, cmd_spec)

            sub_cmds = {}
            sub_cmds_doc = []
            for sub_cmd in cmd_spec["commands"]:
                sub_cmds.update(self._load_single_subcmd(key, sub_cmd))
                id = hashlib.md5(f"s_{key}_{sub_cmd['name']}".encode()).hexdigest()
                sub_cmds_doc.append(DocumentWrapper(
                    id=id,
                    data=sub_cmd["description"],
                    metadata={
                        "binary": key,
                        "type": "subcommand",
                        "name": sub_cmd["name"],
                    },
                ))
            result.update({key: (description, global_options, sub_cmds)})
            VectorDB.add_docs(self.vec_collection, sub_cmds_doc)

            id = hashlib.md5(f"b_{key}".encode()).hexdigest()
            result_doc.append(DocumentWrapper(
                id=id,
                data=description,
                metadata={
                    "name": key,
                    "type": "binary",
                },
            ))

        VectorDB.add_docs(self.vec_collection, result_doc)
        return result
