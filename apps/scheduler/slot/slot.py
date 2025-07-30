# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""参数槽位管理"""

import copy
import json
import logging
import traceback
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator
from jsonschema.validators import extend

from apps.schemas.response_data import ParamsNode
from apps.scheduler.call.choice.schema import Type
from apps.scheduler.slot.parser import (
    SlotConstParser,
    SlotDateParser,
    SlotDefaultParser,
    SlotTimestampParser,
)
from apps.scheduler.slot.util import escape_path, patch_json

logger = logging.getLogger(__name__)

# 各类检查器
_TYPE_CHECKER = [
    SlotDateParser,
    SlotTimestampParser,
]
_FORMAT_CHECKER = []
_KEYWORD_CHECKER = {
    "const": SlotConstParser.keyword_validate,
    "default": SlotDefaultParser.keyword_validate,
}

# 各类转换器
_TYPE_CONVERTER = [
    SlotDateParser,
    SlotTimestampParser,
]
_KEYWORD_CONVERTER = {
    "const": SlotConstParser,
    "default": SlotDefaultParser,
}


class Slot:
    """
    参数槽

    （1）检查提供的JSON和JSON Schema的有效性
    （2）找到不满足要求的JSON字段，并提取成平铺的JSON，交由前端处理
    （3）可对特殊格式的字段进行处理
    """

    def __init__(self, schema: dict) -> None:
        """初始化参数槽处理器"""
        try:
            # 导入所有校验器，动态生成新的类
            self._validator_cls = Slot._construct_validator()
        except Exception as e:
            err = f"Invalid JSON Schema validator: {e!s}\n{traceback.format_exc()}"
            raise ValueError(err) from e

        # 预初始化变量
        self._json = {}

        try:
            # 校验提供的JSON Schema是否合法
            self._validator_cls.check_schema(schema)
        except Exception as e:
            err = f"Invalid JSON Schema: {e!s}"
            raise ValueError(err) from e

        self._validator = self._validator_cls(schema)
        self._schema = schema

    @staticmethod
    def _construct_validator() -> type[Validator]:
        """构造JSON Schema验证器"""
        type_checker = Draft7Validator.TYPE_CHECKER
        # 把所有type_checker都添加
        for checker in _TYPE_CHECKER:
            type_checker = type_checker.redefine(checker.type, checker.type_validate)

        format_checker = Draft7Validator.FORMAT_CHECKER
        # 把所有format_checker都添加
        for checker in _FORMAT_CHECKER:
            format_checker = format_checker.redefine(checker.type, checker.type_validate)

        return extend(
            Draft7Validator, type_checker=type_checker, format_checker=format_checker, validators=_KEYWORD_CHECKER,
        )

    def process_json(self, json_data: str | dict[str, Any]) -> dict[str, Any]:  # noqa: C901
        """将提供的JSON数据进行处理"""
        if isinstance(json_data, str):
            json_data = json.loads(json_data)

        def _process_json_value(json_value: Any, spec_data: dict[str, Any]) -> Any:  # noqa: C901, PLR0911, PLR0912
            """
            使用递归的方式对JSON返回值进行处理

            :param json_value: 返回值中的字段
            :param spec_data: 返回值字段对应的JSON Schema
            :return: 处理后的这部分返回值字段
            """
            if "allOf" in spec_data:
                processed_dict = {}
                for item in spec_data["allOf"]:
                    processed_dict.update(_process_json_value(json_value, item))
                return processed_dict

            for key in ("anyOf", "oneOf"):
                if key in spec_data:
                    for item in spec_data[key]:
                        processed_dict = _process_json_value(json_value, item)
                        if processed_dict is not None:
                            return processed_dict

            if "type" in spec_data:
                if spec_data["type"] == "array" and isinstance(json_value, list):
                    # 若Schema不标准，则不进行处理
                    if "items" not in spec_data:
                        return json_value
                    # Schema标准
                    return [_process_json_value(item, spec_data["items"]) for item in json_value]
                if spec_data["type"] == "object" and isinstance(json_value, dict):
                    # 若Schema不标准，则不进行处理F
                    if "properties" not in spec_data:
                        return json_value
                    # Schema标准
                    processed_dict = {}
                    for key, val in json_value.items():
                        if key not in spec_data["properties"]:
                            processed_dict[key] = val
                            continue
                        processed_dict[key] = _process_json_value(val, spec_data["properties"][key])
                    return processed_dict

                for converter in _TYPE_CONVERTER:
                    # 如果是自定义类型
                    if converter.name == spec_data["type"]:
                        # 如果类型有附加字段
                        if converter.name in spec_data:
                            return converter.convert(json_value, **spec_data[converter.name])
                        return converter.convert(json_value)

            return json_value

        # 遍历JSON，处理每一个字段
        return _process_json_value(json_data, self._schema)

    @staticmethod
    def _generate_example(schema_node: dict) -> Any:  # noqa: PLR0911
        """根据schema生成示例值"""
        if "anyOf" in schema_node or "oneOf" in schema_node:
            # 如果有anyOf，随机返回一个示例
            for item in schema_node["anyOf"] if "anyOf" in schema_node else schema_node["oneOf"]:
                example = Slot._generate_example(item)
                if example is not None:
                    return example

        if "allOf" in schema_node:
            # 如果有allOf，返回所有示例的合并
            example = None
            for item in schema_node["allOf"]:
                if example is None:
                    example = Slot._generate_example(item)
                else:
                    other_example = Slot._generate_example(item)
                    if isinstance(example, dict) and isinstance(other_example, dict):
                        example.update(other_example)
                    else:
                        example = None
                        break
            return example

        if "default" in schema_node:
            return schema_node["default"]

        if "type" not in schema_node:
            return None
        type_value = schema_node["type"]
        if isinstance(type_value, list):
            # 如果是多类型，随机返回一个示例
            if len(type_value) > 1:
                type_value = type_value[0]
        # 处理类型为 object 的节点
        if type_value == "object":
            data = {}
            properties = schema_node.get("properties", {})
            for name, schema in properties.items():
                data[name] = Slot._generate_example(schema)
            return data
        # 处理类型为 array 的节点
        elif type_value == "array":
            items_schema = schema_node.get("items", {})
            return [Slot._generate_example(items_schema)]

        # 处理类型为 string 的节点
        elif type_value == "string":
            return ""

        # 处理类型为 number 或 integer 的节点
        elif type_value in ["number", "integer"]:
            return 0

        # 处理类型为 boolean 的节点
        elif type_value == "boolean":
            return False

        # 处理其他类型或未定义类型
        return None

    def create_empty_slot(self) -> dict[str, Any]:
        """创建一个空的槽位"""
        return self._generate_example(self._schema)

    def extract_type_desc_from_schema(self) -> dict[str, str]:
        """从JSON Schema中提取类型描述"""

        def _extract_type_desc(schema_node: dict[str, Any]) -> dict[str, Any]:
            # 处理组合关键字
            special_keys = ["anyOf", "allOf", "oneOf"]
            for key in special_keys:
                if key in schema_node:
                    data = {
                        "type": key,
                        "description": schema_node.get("description", ""),
                        "items": {},
                    }
                    type_index = 0
                    for item in schema_node[key]:
                        if isinstance(item, dict):
                            data["items"][f"item_{type_index}"] = _extract_type_desc(item)
                        else:
                            data["items"][f"item_{type_index}"] = {"type": item, "description": ""}
                        type_index += 1
                    return data
            # 处理基本类型
            type_val = schema_node.get("type", "")
            description = schema_node.get("description", "")

            # 处理多类型数组
            if isinstance(type_val, list):
                if len(type_val) > 1:
                    data = {"type": "union", "description": description, "items": {}}
                    type_index = 0
                    for t in type_val:
                        if t == "object":
                            tmp_dict = {}
                            for key, val in schema_node.get("properties", {}).items():
                                tmp_dict[key] = _extract_type_desc(val)
                            data["items"][f"item_{type_index}"] = tmp_dict
                        elif t == "array":
                            items_schema = schema_node.get("items", {})
                            data["items"][f"item_{type_index}"] = _extract_type_desc(items_schema)
                        else:
                            data["items"][f"item_{type_index}"] = {"type": t, "description": description}
                        type_index += 1
                    return data
                elif len(type_val) == 1:
                    type_val = type_val[0]
                else:
                    type_val = ""

            data = {"type": type_val, "description": description, " items": {}}

            # 递归处理对象和数组
            if type_val == "object":
                for key, val in schema_node.get("properties", {}).items():
                    data["items"][key] = _extract_type_desc(val)
            elif type_val == "array":
                items_schema = schema_node.get("items", {})
                if isinstance(items_schema, list):
                    item_index = 0
                    for item in items_schema:
                        data["items"][f"item_{item_index}"] = _extract_type_desc(item)
                        item_index += 1
                else:
                    data["items"]["item"] = _extract_type_desc(items_schema)
            if data["items"] == {}:
                del data["items"]
            return data

        return _extract_type_desc(self._schema)

    def get_params_node_from_schema(self, root: str = "") -> ParamsNode:
        """从JSON Schema中提取ParamsNode"""
        def _extract_params_node(schema_node: dict[str, Any], name: str = "", path: str = "") -> ParamsNode:
            """递归提取ParamsNode"""
            if "type" not in schema_node:
                return None

            param_type = schema_node["type"]
            if isinstance(param_type, list):
                return None  # 不支持多类型
            if param_type == "object":
                param_type = Type.DICT
            elif param_type == "array":
                param_type = Type.LIST
            elif param_type == "string":
                param_type = Type.STRING
            elif param_type in ["number", "integer"]:
                param_type = Type.NUMBER
            elif param_type == "boolean":
                param_type = Type.BOOL
            else:
                logger.warning(f"[Slot] 不支持的参数类型: {param_type}")
                return None
            sub_params = []

            if param_type == Type.DICT and "properties" in schema_node:
                for key, value in schema_node["properties"].items():
                    sub_param = _extract_params_node(value, name=key, path=f"{path}/{key}")
                    if sub_param:
                        sub_params.append(sub_param)
            else:
                # 对于非对象类型，直接返回空子参数
                sub_params = None
            return ParamsNode(paramName=name,
                              paramPath=path,
                              paramType=param_type,
                              subParams=sub_params)
        try:
            return _extract_params_node(self._schema, name=root, path=root)
        except Exception as e:
            logger.error(f"[Slot] 提取ParamsNode失败: {e!s}\n{traceback.format_exc()}")
            return None

    def _flatten_schema(self, schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """将JSON Schema扁平化"""
        result = {}
        required = []

        # 合并处理 allOf、anyOf、oneOf
        for key in ("allOf", "anyOf", "oneOf"):
            if key in schema:
                for item in schema[key]:
                    sub_result, sub_required = self._flatten_schema(item)
                    result.update(sub_result)
                    required.extend(sub_required)

        # 处理type
        if "type" in schema:
            if schema["type"] == "object" and "properties" in schema:
                sub_result, sub_required = self._flatten_schema(schema["properties"])
                result.update(sub_result)
                required.extend(sub_required)
            else:
                result[schema["type"]] = schema
                required.append(schema["type"])

        return result, required

    def _strip_error(self, error: ValidationError) -> tuple[dict[str, Any], list[str]]:
        """裁剪发生错误的JSON Schema，并返回可能的附加路径"""
        # required的错误是在上层抛出的，需要裁剪schema
        if error.validator == "required":
            # 从错误信息中提取字段
            try:
                # 注意：此处与Validator文本有关，注意版本问题
                key = error.message.split("'")[1]
            except IndexError:
                logger.exception("[Slot] 错误信息不合法: %s", error.message)
                return {}, []

            # 如果字段存在，则返回裁剪后的schema
            if isinstance(error.schema, Mapping) and "properties" in error.schema and key in error.schema["properties"]:
                schema = error.schema["properties"][key]
                # 将默认值改为当前值
                schema["default"] = ""
                return schema, [key]

            # 如果字段不存在，则返回空
            logger.exception("[Slot] 错误schema不合法: %s", error.schema)
            return {}, []

        # 默认无需裁剪
        if isinstance(error.schema, Mapping):
            return dict(error.schema.items()), []

        logger.exception("[Slot] 错误schema不合法: %s", error.schema)
        return {}, []

    def _assemble_patch(
            self,
            key: str,
            val: Any,
            json_data: Any,
            schema: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """将用户手动填充的参数专为真实JSON"""
        patch_list = []
        key_path = key.split("/")

        current_path = "/"
        current_schema = schema
        for path in key_path:
            if path == "":
                # 空路径，跳过
                continue
            if (current_path + path) == key:
                # 当前路径与key相同，直接返回
                patch_list.append({"op": "add", "path": current_path + path, "value": val})
                return patch_list

            # 如果是数字，访问元素
            if path.isdigit() and isinstance(json_data, list):
                try:
                    json_data = json_data[int(path)]
                    current_schema = current_schema["items"]
                except (IndexError, KeyError):
                    # 检测当前数组元素的类型，并建一个空值
                    empty_value = self._generate_example(current_schema["items"])
                    patch_list.append({"op": "add", "path": current_path + "-", "value": [empty_value]})
                    json_data = empty_value
                    current_schema = current_schema["items"]
            # 如果是字符串，访问对象
            elif isinstance(json_data, dict):
                try:
                    json_data = json_data[path]
                    current_schema = current_schema["properties"][path]
                except (KeyError, IndexError):
                    patch_list.append({"op": "add", "path": current_path + path, "value": {}})
                    json_data = {}
                    current_schema = current_schema["properties"][path]
            else:
                err = f"[Slot] 错误的路径: {key}"
                logger.exception(err)
                raise ValueError(err)

            current_path = current_path + path + "/"

        logger.info("[Slot] 组装patch: %s", patch_list)
        return patch_list

    def convert_json(self, json_data: str | dict[str, Any]) -> dict[str, Any]:
        """将用户手动填充的参数专为真实JSON"""
        json_dict = json.loads(json_data) if isinstance(json_data, str) else json_data
        final_json = {}

        # 对JSON进行处理
        for key, val in json_dict.items():
            # 如果是patch，则构建
            if key[0] == "/":
                patch_list = self._assemble_patch(key, val, final_json, self._schema)
                final_json = patch_json(patch_list, final_json)
            else:
                final_json[key] = val

        return final_json

    def check_json(self, json_data: dict[str, Any]) -> dict[str, Any]:
        """检测槽位是否合法、是否填充完成"""
        empty = True
        schema_template = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        for error in self._validator.iter_errors(json_data):
            # 如果有错误，说明填充参数不通过
            empty = False

            # 处理错误
            slot_schema, additional_path = self._strip_error(error)
            # 组装JSON Pointer
            pointer = "/" + "/".join([escape_path(str(v)) for v in error.path])
            if additional_path:
                pointer = pointer.rstrip("/") + "/" + "/".join(additional_path)
            schema_template["properties"][pointer] = slot_schema
            schema_template["required"].append(pointer)

        # 如果有错误
        if not empty:
            return schema_template

        return {}

    def add_null_to_basic_types(self) -> dict[str, Any]:
        """
        递归地为 JSON Schema 中的基础类型（bool、number等）添加 null 选项
        """
        def add_null_to_basic_types(schema: dict[str, Any]) -> dict[str, Any]:
            """
                递归地为 JSON Schema 中的基础类型（bool、number等）添加 null 选项

                参数:
                schema (dict): 原始 JSON Schema

                返回:
                dict: 修改后的 JSON Schema
            """
            # 如果不是字典类型（schema），直接返回
            if not isinstance(schema, dict):
                return schema

            # 处理当前节点的 type 字段
            if 'type' in schema:
                # 处理单一类型字符串
                if isinstance(schema['type'], str):
                    if schema['type'] in ['boolean', 'number', 'string', 'integer']:
                        schema['type'] = [schema['type'], 'null']

                # 处理类型数组
                elif isinstance(schema['type'], list):
                    for i, t in enumerate(schema['type']):
                        if isinstance(t, str) and t in ['boolean', 'number', 'string', 'integer']:
                            if 'null' not in schema['type']:
                                schema['type'].append('null')
                            break

            # 递归处理 properties 字段（对象类型）
            if 'properties' in schema:
                for prop, prop_schema in schema['properties'].items():
                    schema['properties'][prop] = add_null_to_basic_types(prop_schema)

            # 递归处理 items 字段（数组类型）
            if 'items' in schema:
                schema['items'] = add_null_to_basic_types(schema['items'])

            # 递归处理 anyOf, oneOf, allOf 字段
            for keyword in ['anyOf', 'oneOf', 'allOf']:
                if keyword in schema:
                    schema[keyword] = [add_null_to_basic_types(sub_schema) for sub_schema in schema[keyword]]

            return schema
        schema_copy = copy.deepcopy(self._schema)
        return add_null_to_basic_types(schema_copy)
