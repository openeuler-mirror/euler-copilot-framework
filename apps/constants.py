"""常量数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from __future__ import annotations

import logging

# 新对话默认标题
NEW_CHAT = "New Chat"
# 滑动窗口限流 默认窗口期
SLIDE_WINDOW_TIME = 60
# 滑动窗口限流 最大请求数
SLIDE_WINDOW_QUESTION_COUNT = 10
# API Call 最大返回值长度（字符）
MAX_API_RESPONSE_LENGTH = 8192
# Scheduler最大历史轮次
MAX_SCHEDULER_HISTORY_SIZE = 3
# 语义接口目录中工具子目录
CALL_DIR = "call"
# 语义接口目录中服务子目录
SERVICE_DIR = "service"
# 语义接口目录中应用子目录
APP_DIR = "app"
# 日志记录器
LOGGER = logging.getLogger("ray")

REASONING_BEGIN_TOKEN = [
    "<think>",
]
REASONING_END_TOKEN = [
    "</think>",
]
