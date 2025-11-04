# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""主程序"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_profiler import Profiler
from rich.console import Console
from rich.logging import RichHandler

from .common.config import config
from .common.postgres import postgres
from .routers import (
    appcenter,
    auth,
    blacklist,
    chat,
    comment,
    conversation,
    document,
    flow,
    health,
    llm,
    mcp_service,
    parameter,
    record,
    service,
    tag,
    user,
)
from .scheduler.pool.pool import pool
from .services.settings import SettingsManager


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时初始化资源
    await postgres.init()
    await pool.init()
    # 初始化全局LLM设置
    await SettingsManager.init_global_llm_settings()
    yield
    # 关闭时释放资源
    await postgres.close()


# 定义FastAPI app
app = FastAPI(redoc_url=None, lifespan=lifespan)
Profiler(app)

# 定义FastAPI全局中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.fastapi.domain],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 关联API路由
app.include_router(appcenter.router)
app.include_router(auth.admin_router)
app.include_router(auth.router)
app.include_router(blacklist.admin_router)
app.include_router(blacklist.router)
app.include_router(chat.router)
app.include_router(comment.router)
app.include_router(conversation.router)
app.include_router(document.router)
app.include_router(flow.router)
app.include_router(health.router)
app.include_router(llm.router)
app.include_router(llm.admin_router)
app.include_router(mcp_service.router)
app.include_router(mcp_service.admin_router)
app.include_router(parameter.router)
app.include_router(record.router)
app.include_router(service.router)
app.include_router(service.admin_router)
app.include_router(tag.admin_router)
app.include_router(user.router)

# logger配置
LOGGER_FORMAT = "%(funcName)s() - %(message)s"
DATE_FORMAT = "%y-%b-%d %H:%M:%S"
logging.basicConfig(
    level=logging.INFO,
    format=LOGGER_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[RichHandler(rich_tracebacks=True, console=Console(
        color_system="256",
        width=160,
    ))],
)


# 运行
if __name__ == "__main__":
    # 启动FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info", log_config=None)
