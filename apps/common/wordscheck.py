# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from __future__ import annotations

import http
import re
import logging

import requests

from apps.common.config import config

logger = logging.getLogger('gunicorn.error')


class APICheck(object):

    @classmethod
    def check(cls, content: str) -> int:
        url = config['WORDS_CHECK']
        headers = {"Content-Type": "application/json"}
        data = {"content": content}
        try:
            response = requests.post(url=url, json=data, headers=headers, timeout=10)
            if response.status_code == http.HTTPStatus.OK:
                if re.search("ok", str(response.content)):
                    return 1
            return 0
        except Exception as e:
            logger.info("过滤敏感词错误：" + str(e))
            return -1


class KeywordCheck:
    words_list: list

    def __init__(self):
        with open(config["WORDS_LIST"], "r", encoding="utf-8") as f:
            self.words_list = f.read().splitlines()

    def check_words(self, message: str) -> int:
        if message in self.words_list:
            return 1
        return 0


class WordsCheck:
    tool: APICheck | KeywordCheck | None = None

    def __init__(self):
        raise NotImplementedError("WordsCheck无法被实例化！")

    @classmethod
    def init(cls):
        if config["DETECT_TYPE"] == "keyword":
            cls.tool = KeywordCheck()
        elif config["DETECT_TYPE"] == "wordscheck":
            cls.tool = APICheck()
        else:
            cls.tool = None

    @classmethod
    async def check(cls, message: str) -> int:
        # 异常-1，拦截0，正常1
        if not cls.tool:
            return 1
        return cls.tool.check(message)
