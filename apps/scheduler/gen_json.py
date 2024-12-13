# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

from typing import List


# 检查API是否需要上传文件；当前不支持文件上传嵌套进表单object内的情况
def check_upload_file(schema: dict, available_files: List[str]) -> dict:
    file_details = {
        "type": "object",
        "properties": {}
    }

    pattern = "("
    for name in available_files:
        pattern += name + "|"
    pattern = pattern[:-1] + ")"

    for key, val in schema.items():
        if "format" in val and val["format"] == "binary":
            file_details["properties"][key] = {
                "type": "string",
                "pattern": pattern
            }
        if val["type"] == "array":
            if "format" in val["items"] and val["items"]["format"] == "binary":
                file_details["properties"][key] = {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": pattern
                    },
                    "minItems": 1
                }
    return file_details


# 处理字符串中的特殊字符
def _process_string(string: str) -> str:
    string = string.replace("$", r"\$")
    string = string.replace("{", r"\{")
    string = string.replace("}", r"\}")
    # string = string.replace(".", r"\.")
    string = string.replace("[", r"\[")
    string = string.replace("]", r"\]")
    string = string.replace("(", r"\(")
    string = string.replace(")", r"\)")
    string = string.replace("|", r"\|")
    string = string.replace("?", r"\?")
    string = string.replace("*", r"\*")
    string = string.replace("+", r"\+")
    string = string.replace("\\", "\\\\")
    string = string.replace("^", r"\^")
    return string


# 生成JSON正则字段；不支持主动$ref语法；不支持oneOf；allOf只支持1个schema的情况
def gen_json(schema: dict) -> str:
    if "anyOf" in schema:
        regex = "("
        for item in schema["anyOf"]:
            regex += gen_json(item)
            regex += "|"
        regex = regex.rstrip("|") + ")"
        return regex

    if "allOf" in schema:
        if len(schema["allOf"]) != 1:
            raise NotImplementedError("allOf只支持1个schema的情况")
        return gen_json(schema["allOf"][0])

    if "enum" in schema:
        choice_regex = ""
        for item in schema["enum"]:
            if schema["type"] == "boolean":
                if item is True:
                    choice_regex += "true"
                else:
                    choice_regex += "false"
            elif schema["type"] == "string":
                choice_regex += "\"" + _process_string(str(item)) + "\""
            else:
                choice_regex += _process_string(str(item))
            choice_regex += "|"
        return '(' + choice_regex.rstrip("|") + '),'

    if "pattern" in schema:
        if schema["type"] == "string":
            return "\"" + schema["pattern"] + "\","
        return schema["pattern"] + ","

    if "type" in schema:
        # 布尔类型，例子：true
        if schema["type"] == "boolean":
            return r"(true|false),"
        # 整数类型，例子：-100；最多支持9位
        if schema["type"] == "integer":
            return r"[-\+]?[\d]{0,9},"
        # 浮点数类型，例子：-1.2e+10；每一段数字最多支持9位
        if schema["type"] == "number":
            return r"""[-\+]?[\d]{0,9}[.][\d]{0,9}(e[-\+]?[\d]{0,9})?,"""
        # 字符串类型，例子：最小长度0，最大长度10
        if schema["type"] == "string":
            regex = r'"([^"\\\x00-\x1F\x7F-\x9F]|\\["\\])'
            min_len = schema.get("minLength", 0)
            regex += "{" + str(min_len)
            if "maxLength" in schema:
                if schema["maxLength"] < min_len:
                    raise ValueError("字符串最大长度不能小于最小长度")
                regex += "," + str(schema["maxLength"]) + "}\","
            else:
                regex += ",}\","
            return regex
        # 数组
        if schema["type"] == "array":
            min_len = schema.get("minItems", 0)
            max_len = schema.get("maxItems", None)
            if isinstance(max_len, int) and min_len > max_len:
                raise ValueError("数组最大长度不能小于最小长度")
            return _json_array(schema, min_len, max_len)
        # 对象
        if schema["type"] == "object":
            regex = _json_object(schema)
            return regex


# 数组：暂时不支持PrefixItems；只支持数组中数据结构都一致的情况
def _json_array(schema: dict, min_len: int, max_len: int | None) -> str:
    if max_len is None:
        num_repeats = rf"{{{max(min_len - 1, 0)},}}"
    else:
        num_repeats =  rf"{{{max(min_len - 1, 0)},{max_len - 1}}}"

    item_regex = gen_json(schema["items"]).rstrip(",")
    if not item_regex:
        return ""

    regex = rf"\[(({item_regex})(,{item_regex}){num_repeats})?\],"
    return regex


def _json_object(schema: dict) -> str:
    if "required" in schema:
        required = schema["required"]
    else:
        required = []

    regex = r'\{'

    if "additionalProperties" in schema:
        regex += gen_json({"type": "string"}) + "[ ]?:[ ]?" + gen_json(schema["additionalProperties"])

    if "properties" in schema:
        for key, val in schema["properties"].items():
            current_regex = gen_json(val)
            if not current_regex:
                continue

            regex += r'[ ]?"' + _process_string(key) + r'"[ ]?:[ ]?'
            if key not in required:
                regex += r"(null|" + current_regex.rstrip(",") + "),"
            else:
                regex += current_regex

    regex = regex.rstrip(",") + r'[ ]?\}'
    return regex
