# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""常量数据"""

from anyio import Path

from .common.config import config

# 新对话默认标题
NEW_CHAT = "新对话"
# 滑动窗口限流 默认窗口期
SLIDE_WINDOW_TIME = 15
# OIDC 访问Token 过期时间（分钟）
OIDC_ACCESS_TOKEN_EXPIRE_TIME = 30
# OIDC 刷新Token 过期时间（分钟）
OIDC_REFRESH_TOKEN_EXPIRE_TIME = 180
# 滑动窗口限流 最大请求数（按单个用户统计）
SLIDE_WINDOW_QUESTION_COUNT = 5
# 全局同时运行任务上限（与用户无关）
MAX_CONCURRENT_TASKS = 30
# API Call 最大返回值长度（字符）
MAX_API_RESPONSE_LENGTH = 8192
# Session时间，单位为分钟
SESSION_TTL = 30 * 24 * 60
# JSON生成最大尝试次数
JSON_GEN_MAX_TRIAL = 3
# 应用默认历史轮次
APP_DEFAULT_HISTORY_LEN = 3
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
MCP_PATH = Path(config.deploy.data_dir) / "semantics" / "mcp"
# 项目路径
PROJ_PATH = Path(__file__).parent.parent
# 图标存储位置
ICON_PATH = PROJ_PATH / "static" / "icons"
# MCP Agent 最大重试次数
AGENT_MAX_RETRY_TIMES = 3
# MCP Agent 最大步骤数
AGENT_MAX_STEPS = 25
# MCP Agent 最终步骤名称
AGENT_FINAL_STEP_NAME = "FINAL"
# 大模型超时时间
LLM_TIMEOUT = 300.0
