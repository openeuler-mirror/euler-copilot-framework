"""敏感词检查模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import http
import logging
import re

import aiofiles
import aiohttp
import ray

from apps.common.config import config

logger = logging.getLogger(__name__)

@ray.remote
class WordsCheck:
    """敏感词检查工具"""

    async def _init_file(self) -> None:
        """初始化关键词列表"""
        async with aiofiles.open(config["WORDS_LIST"], encoding="utf-8") as f:
            self.words_list = (await f.read()).splitlines()

    async def _check_wordlist(self, message: str) -> int:
        """使用关键词列表检查敏感词"""
        if message in self.words_list:
            return 1
        return 0

    async def _check_api(self, message: str) -> int:
        """使用API接口检查敏感词"""
        url = config["WORDS_CHECK"]
        if url is None:
            err = "配置文件中未设置WORDS_CHECK"
            raise ValueError(err)

        headers = {"Content-Type": "application/json"}
        data = {"content": message}
        try:
            async with aiohttp.ClientSession() as session, session.post(url=url, json=data, headers=headers, timeout=10) as response:
                if response.status == http.HTTPStatus.OK and re.search("ok", str(response.content)):
                    return 1
                return 0
        except Exception:
            logger.exception("[WordsCheck] 过滤敏感词错误")
            return -1

    async def init(self) -> None:
        """初始化敏感词检查器"""
        if config["DETECT_TYPE"] == "keyword":
            await self._init_file()

    async def check(self, message: str) -> int:
        """检查消息是否包含关键词

        异常-1，拦截0，正常1
        """
        if config["DETECT_TYPE"] == "keyword":
            return await self._check_wordlist(message)
        if config["DETECT_TYPE"] == "wordscheck":
            return await self._check_api(message)
        # 不设置检查类型，默认不拦截
        return 1
