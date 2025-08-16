"""
常量数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from anyio import Path

from apps.common.config import Config

# 新对话默认标题
NEW_CHAT = "新对话"
# 滑动窗口限流 默认窗口期
SLIDE_WINDOW_TIME = 15
# OIDC 访问Token 过期时间（分钟）
OIDC_ACCESS_TOKEN_EXPIRE_TIME = 30
# OIDC 刷新Token 过期时间（分钟）
OIDC_REFRESH_TOKEN_EXPIRE_TIME = 180
# 滑动窗口限流 最大请求数
SLIDE_WINDOW_QUESTION_COUNT = 10
# API Call 最大返回值长度（字符）
MAX_API_RESPONSE_LENGTH = 8192
# Executor最大步骤历史数
STEP_HISTORY_SIZE = 3
# Session时间，单位为分钟
SESSION_TTL = 30 * 24 * 60
# JSON生成最大尝试次数
JSON_GEN_MAX_TRIAL = 3
# 推理开始标记
REASONING_BEGIN_TOKEN = [
    "<think>",
]
# 推理结束标记
REASONING_END_TOKEN = [
    "</think>",
]
# 插件中心每页卡片数量
SERVICE_PAGE_SIZE = 16
# 图标允许的MIME类型
ALLOWED_ICON_MIME_TYPES = [
    "image/png",
    "image/jpeg",
    "image/avif",
    "image/heic",
    "image/heif",
    "image/webp",
    "image/bmp",
    "image/tiff",
]
# MCP路径
MCP_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp"
# 项目路径
PROJ_PATH = Path(__file__).parent.parent
# 图标存储
ICON_PATH = PROJ_PATH / "static" / "icons"
