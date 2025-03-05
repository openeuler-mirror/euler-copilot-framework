"""常量数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from __future__ import annotations

import logging

CURRENT_REVISION_VERSION = "0.0.0"
NEW_CHAT = "New Chat"
SLIDE_WINDOW_TIME = 60
SLIDE_WINDOW_QUESTION_COUNT = 10
MAX_SCHEDULER_HISTORY_SIZE = 3

LOGGER = logging.getLogger("gunicorn.error")

REASONING_BEGIN_TOKEN = [
    "<think>",
]
REASONING_END_TOKEN = [
    "</think>",
]
