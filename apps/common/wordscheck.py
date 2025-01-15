"""敏感词检查模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import base64
import hashlib
import hmac
import http
import json
import re
import uuid
from datetime import datetime
from typing import Any, Optional, Union

import pytz
import requests
from fastapi import status

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


class SCAS:
    """使用SCAS接口检查敏感词"""

    app_id: Optional[str]
    sign_key: Optional[str]
    business_id: Optional[str]
    scene_id: Optional[str]
    url: str
    retry: int = 2
    timeout: int = 3
    count: int = 0
    enable: bool = True
    THRESHOLD: int = 100

    def __init__(self) -> None:
        """初始化SCAS"""
        self.app_id = config["SCAS_APP_ID"]
        if self.app_id is None:
            err = "配置文件中未设置SCAS_APP_ID"
            raise ValueError(err)

        self.sign_key = config["SCAS_SIGN_KEY"]
        if self.sign_key is None:
            err = "配置文件中未设置SCAS_SIGN_KEY"
            raise ValueError(err)

        self.business_id = config["SCAS_BUSINESS_ID"]
        if self.business_id is None:
            err = "配置文件中未设置SCAS_BUSINESS_ID"
            raise ValueError(err)

        self.scene_id = config["SCAS_SCENE_ID"]
        if self.scene_id is None:
            err = "配置文件中未设置SCAS_SCENE_ID"
            raise ValueError(err)

        self.url = config["SCAS_URL"] + "/scas/v1/textIdentify"
        if self.url is None:
            err = "配置文件中未设置SCAS_URL"
            raise ValueError(err)

    def _make_auth_header(self, request: str, time: datetime) -> str:
        """生成认证头"""
        auth_param = 'CLOUDSOA-HMAC-SHA256 appid={}, timestamp={}, signature="{}"'
        sign_format = "{}&{}&{}&{}&appid={}&timestamp={}"

        current_timestamp = int(time.timestamp() * 1000)

        sign_str = sign_format.format("POST", "/scas/v1/textIdentify", "", request,
                                      self.app_id, current_timestamp)
        if self.sign_key is None:
            err = "配置文件中未设置SCAS_SIGN_KEY"
            raise ValueError(err)

        sign_value = base64.b64encode(
            hmac.new(
                bytes.fromhex(self.sign_key),
                bytes(sign_str, "utf-8"),
                hashlib.sha256,
            ).digest()).decode("utf-8")

        return auth_param.format(self.app_id, current_timestamp, sign_value)

    def _make_request_body(self, message: str) -> tuple[dict[str, Any], str]:
        """生成SCAS请求体"""
        if not message:
            return {}, ""

        task_id = str(uuid.uuid4())

        current_time = datetime.now(pytz.timezone("Asia/Shanghai"))
        timestamp = current_time.isoformat(sep=" ", timespec="milliseconds")[:-6]
        timestamp += current_time.strftime("%z")

        post_data = {
            "taskID": task_id,
            "message": {
                "text": message,
            },
            "businessID": self.business_id,
            "sceneID": self.scene_id,
            "uid": "-1",
            "reqTime": timestamp,
            "returnCleanText": 0,
            "loginType": "WEB",
        }
        header = self._make_auth_header(json.dumps(post_data), current_time)

        return post_data, header

    def _post_with_retry(self, post_data: dict[str, Any], header: str) -> Optional[requests.Response]:
        for _ in range(self.retry):
            try:
                return requests.post(self.url, json=post_data, headers={
                    "Content-Type": "application/json",
                    "Authorization": header,
                }, timeout=self.timeout)
            except Exception as e:  # noqa: PERF203
                LOGGER.error(f"检查敏感词错误：{e!s}")
                continue
        return None

    def _check_message(self, message: str) -> int:  # noqa: PLR0911
        """使用SCAS检查敏感词"""
        # -1: 异常，0: 不通过，1: 通过
        post_data, header = self._make_request_body(message)
        if not post_data and not header:
            LOGGER.info("待审核信息错误")
            return -1

        req = self._post_with_retry(post_data, header)
        if req is None:
            LOGGER.info("风控接口调用参数错误")
            return -1

        if req.status_code != status.HTTP_200_OK:
            LOGGER.info(f"风控HTTP错误：{req.status_code}")
            return -1

        return_data = req.json()
        if "resultCode" not in return_data or "securityResult" not in return_data:
            LOGGER.info("风控接口返回错误")
            return -1

        if return_data["resultCode"]:
            LOGGER.info("风控处理错误：{}".format(return_data["resultCode"]))
            return -1

        if return_data["securityResult"] == "ACCEPT":
            return 1
        return 0

    def check(self, message: str) -> int:
        """使用SCAS检查消息"""
        ret = self._check_message(message)
        if ret == -1:
            if not self.enable:
                # 放通
                return 1
            self.count += 1
            if self.count >= self.THRESHOLD:
                self.enable = False
        else:
            self.enable = True
            self.count = 0
        return ret


class KeywordCheck:
    """使用关键词列表检查敏感词"""

    words_list: list

    def __init__(self) -> None:
        """初始化关键词列表"""
        with open(config["WORDS_LIST"], encoding="utf-8") as f:
            self.words_list = f.read().splitlines()

    def check(self, message: str) -> int:
        """使用关键词列表检查关键词"""
        if message in self.words_list:
            return 1
        return 0


class WordsCheck:
    """敏感词检查工具"""

    tool: Union[APICheck, KeywordCheck, SCAS, None] = None

    @classmethod
    def init(cls) -> None:
        """初始化敏感词检查器"""
        if config["DETECT_TYPE"] == "scas":
            cls.tool = SCAS()
        elif config["DETECT_TYPE"] == "keyword":
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
