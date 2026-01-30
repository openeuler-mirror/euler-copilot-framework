# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""常量数据"""

from anyio import Path

from .common.config import config

# 新对话默认标题
NEW_CHAT = "新对话"
# 滑动窗口限流 默认窗口期
SLIDE_WINDOW_TIME = 15
# 滑动窗口限流 最大请求数（按单个用户统计）
SLIDE_WINDOW_QUESTION_COUNT = 5
# 全局同时运行任务上限（与用户无关）
MAX_CONCURRENT_TASKS = 30
# 应用默认历史轮次
APP_DEFAULT_HISTORY_LEN = 3
# 插件中心每页卡片数量
SERVICE_PAGE_SIZE = 16
# MCP路径
MCP_PATH = Path(config.deploy.data_dir) / "semantics" / "mcp"
# 大模型超时时间
LLM_TIMEOUT = 300.0
# 对话标题最大长度
CONVERSATION_TITLE_MAX_LENGTH = 30
# Agent最大执行步数
AGENT_MAX_STEPS = 25
