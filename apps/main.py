"""
主程序

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console
from rich.logging import RichHandler

from apps.common.config import Config
from apps.common.lance import LanceDB
from apps.common.wordscheck import WordsCheck
from apps.llm.token import TokenCalculator
from apps.routers import (
    api_key,
    appcenter,
    auth,
    blacklist,
    chat,
    comment,
    conversation,
    document,
    flow,
    health,
    knowledge,
    llm,
    mcp_service,
    record,
    service,
    user,
    parameter
)
from apps.scheduler.pool.pool import Pool

# 定义FastAPI app
app = FastAPI(redoc_url=None)
# 定义FastAPI全局中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config().get_config().fastapi.domain],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 关联API路由
app.include_router(conversation.router)
app.include_router(auth.router)
app.include_router(api_key.router)
app.include_router(appcenter.router)
app.include_router(service.router)
app.include_router(comment.router)
app.include_router(record.router)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(blacklist.router)
app.include_router(document.router)
app.include_router(knowledge.router)
app.include_router(llm.router)
app.include_router(mcp_service.router)
app.include_router(flow.router)
app.include_router(user.router)
app.include_router(parameter.router)

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


async def add_no_auth_user() -> None:
    """
    添加无认证用户
    """
    from apps.common.mongo import MongoDB
    from apps.schemas.collection import User
    mongo = MongoDB()
    user_collection = mongo.get_collection("user")
    await user_collection.insert_one(User(
        _id=Config().get_config().no_auth.user_sub,
        is_admin=True,
    ).model_dump(by_alias=True))


async def init_resources() -> None:
    """初始化必要资源"""
    WordsCheck()
    await LanceDB().init()
    await Pool.init()
    TokenCalculator()
    if Config().get_config().no_auth.enable:
        await add_no_auth_user()

# 运行
if __name__ == "__main__":
    # 初始化必要资源
    asyncio.run(init_resources())

    # 启动FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info", log_config=None)
