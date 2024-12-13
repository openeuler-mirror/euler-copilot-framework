# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List

import sglang

from apps.common.config import config
from apps.scheduler.gen_json import gen_json
from apps.llm import get_scheduler


class Files:
    mapping_lock = threading.Lock()
    mapping: Dict[str, Dict[str, Any]] = {}
    timeout: int = 24 * 60 * 60

    def __init__(self):
        raise RuntimeError("Files类不需要实例化")

    @classmethod
    def add(cls, file_id: str, file_metadata: Dict[str, Any]):
        cls.mapping_lock.acquire()
        cls.mapping[file_id] = file_metadata
        cls.mapping_lock.release()

    @classmethod
    def _check_metadata(cls, file_id: str, metadata: Dict[str, Any]) -> bool:
        if os.path.exists(os.path.join(config["TEMP_DIR"], metadata["path"])):
            return True
        else:
            cls.mapping_lock.acquire()
            cls.mapping.pop(file_id, None)
            cls.mapping_lock.release()
            return False

    """
    样例：
    {
      "time": 1720840438.8062727,
      "name": "test.txt",
      "path": "/tmp/7fbe0b8f-ea8d-4ab9-a1cf-a4661bcd07bb.txt"
    }
    """
    @classmethod
    def get_by_id(cls, file_id: str) -> Dict[str, Any] | None:
        metadata = cls.mapping.get(file_id, None)
        if metadata is None:
            return None
        else:
            if cls._check_metadata(file_id, metadata):
                return metadata
            else:
                return None

    @classmethod
    def get_by_name(cls, file_name: str) -> Dict[str, Any] | None:
        metadata = None
        for key, val in cls.mapping.items():
            if file_name == val.get("name"):
                metadata = val

        if metadata is None:
            return None
        else:
            if cls._check_metadata(file_name, metadata):
                return metadata
            else:
                return None

    @classmethod
    def delete_old_files(cls):
        cls.mapping_lock.acquire()
        popped_key = []
        for key, val in cls.mapping.items():
            if time.time() - val["time"] >= cls.timeout:
                popped_key.append(key)
                continue
            if not cls._check_metadata(key, val):
                popped_key.append(key)
                continue
        for key in popped_key:
            cls.mapping.pop(key)
        cls.mapping_lock.release()


# 通过工具名称选择文件
def choose_file(file_names: List[str], file_spec: dict, question: str, background: str, tool_usage: str):
    def __choose_file(s):
        s += sglang.system("""You are a helpful assistant who can select the files needed by the tool based on the tool's usage and the user's instruction.

    EXAMPLE
    **Context:**
    此时为第一次调用工具，无上下文信息。

    **Instruction:**
    帮我将上传的txt文件和Excel文件转换为Word文档

    **Tool Usage:**
    获取用户上传文件，并将其转换为Word。

    **Avaliable Files:**
    ["1.txt", "log.txt", "sample.xlsx"]

    **Schema:**
    {"type": "object", "properties": {"file_xlsx": {"type": "string", "pattern": "(1.txt|log.txt|sample.xlsx)"}, "file_txt": {"type": "array", "items": {"type": "string", "pattern": "(1.txt|log.txt|sample.xlsx)"}, "minItems": 1}}}

    Output:
    {"file_xlsx": "sample.xlsx", "file_txt": ["1.txt", "log.txt"]}""")
        s += sglang.user(f"""**Context:**
    {background}

    **Instruction:**
    {question}

    **Tool Usage:**
    {tool_usage}

    **Available Files:**
    {file_names}

    **Schema:**
    {json.dumps(file_spec, ensure_ascii=False)}""")

        s += sglang.assistant("Output:\n" + sglang.gen(max_tokens=300, name="files", regex=gen_json(file_spec)))

    backend = get_scheduler()
    if isinstance(backend, sglang.RuntimeEndpoint):
        sglang.set_default_backend(backend)

        return sglang.function(__choose_file)()["files"]
    else:
        return []
