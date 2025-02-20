"""敏感词检查模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import http
import re
from pathlib import Path
from typing import Union

import requests

from apps.common.config import config
from apps.constants import LOGGER


class APICheck:
    """使用API接口检查敏感词"""

    @classmethod
    def check(cls, content: str) -> int:
        """检查敏感词"""
        url = config["WORDS_CHECK"]
        if url is None:
            err = "配置文件中未设置WORDS_CHECK"
            raise ValueError(err)

        headers = {"Content-Type": "application/json"}
        data = {"content": content}
        try:
            response = requests.post(url=url, json=data, headers=headers, timeout=10)
            if response.status_code == http.HTTPStatus.OK and re.search("ok", str(response.content)):
                return 1
            return 0
        except Exception as e:
            LOGGER.info("过滤敏感词错误：" + str(e))
            return -1

class KeywordCheck:
    """使用关键词列表检查敏感词"""

    words_list: list

    def __init__(self) -> None:
        """初始化关键词列表"""
        with Path(config["WORDS_LIST"]).open("r", encoding="utf-8") as f:
            self.words_list = f.read().splitlines()

    def check(self, message: str) -> int:
        """使用关键词列表检查关键词"""
        if message in self.words_list:
            return 1
        return 0


class WordsCheck:
    """敏感词检查工具"""

    tool: Union[APICheck, KeywordCheck, None] = None

    @classmethod
    def init(cls) -> None:
        """初始化敏感词检查器"""
        if config["DETECT_TYPE"] == "keyword":
            cls.tool = KeywordCheck()
        elif config["DETECT_TYPE"] == "wordscheck":
            cls.tool = APICheck()
        else:
            cls.tool = None

    @classmethod
    async def check(cls, message: str) -> int:
        """检查消息是否包含关键词

        异常-1，拦截0，正常1
        """
        if not cls.tool:
            return 1
        return cls.tool.check(message)
