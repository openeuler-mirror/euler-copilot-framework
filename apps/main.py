# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import logging

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.common.config import config
from apps.cron.delete_user import DeleteUserCron
from apps.dependency.session import VerifySessionMiddleware
from apps.logger import log_config
from apps.models.redis import RedisConnectionPool
from apps.routers import (
    api_key,
    auth,
    blacklist,
    chat,
    client,
    comment,
    conversation,
    file,
    health,
    plugin,
    record,
)
from apps.scheduler.files import Files

# 定义FastAPI app
app = FastAPI(docs_url=None, redoc_url=None)
# 定义FastAPI全局中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config['WEB_FRONT_URL']],
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
app.include_router(file.router)
# 初始化日志记录器
logger = logging.getLogger('gunicorn.error')
# 初始化后台定时任务
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(DeleteUserCron.delete_user, 'cron', hour=3)
scheduler.add_job(Files.delete_old_files, 'cron', hour=3)
# 初始化Redis连接池
RedisConnectionPool.get_redis_pool()


if __name__ == "__main__":
    try:
        ssl_enable = config["SSL_ENABLE"]
        if ssl_enable:
            uvicorn.run(
                app,
                host=config["UVICORN_HOST"],
                port=int(config["UVICORN_PORT"]),
                log_config=log_config,
                ssl_certfile=config["SSL_CERTFILE"],
                ssl_keyfile=config["SSL_KEYFILE"],
                ssl_keyfile_password=config["SSL_KEY_PWD"]
            )
        else:
            uvicorn.run(
                app,
                host=config["UVICORN_HOST"],
                port=int(config["UVICORN_PORT"]),
                log_config=log_config
            )
    except Exception as e:
        logger.error(e)
