"""主程序

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.common.config import config
from apps.cron.delete_user import DeleteUserCron
from apps.dependency.session import VerifySessionMiddleware
from apps.routers import (
    api_key,
    auth,
    blacklist,
    chat,
    client,
    comment,
    conversation,
    document,
    health,
    knowledge,
    plugin,
    record,
)

# 定义FastAPI app
app = FastAPI(docs_url=None, redoc_url=None)
# 定义FastAPI全局中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config["DOMAIN"]],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(VerifySessionMiddleware)
# 关联API路由
app.include_router(conversation.router)
app.include_router(auth.router)
app.include_router(api_key.router)
app.include_router(comment.router)
app.include_router(record.router)
app.include_router(health.router)
app.include_router(plugin.router)
app.include_router(chat.router)
app.include_router(client.router)
app.include_router(blacklist.router)
app.include_router(document.router)
app.include_router(knowledge.router)
# 初始化后台定时任务
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(DeleteUserCron.delete_user, "cron", hour=3)
