"""主程序

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from __future__ import annotations

import logging

import ray
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ray import serve
from ray.serve.config import HTTPOptions

from apps.common.config import config
from apps.common.task import Task
from apps.common.wordscheck import WordsCheck
from apps.constants import SCHEDULER_REPLICAS
from apps.cron.delete_user import DeleteUserCron
from apps.dependency.session import VerifySessionMiddleware
from apps.routers import (
    api_key,
    appcenter,
    auth,
    blacklist,
    chat,
    client,
    comment,
    conversation,
    document,
    flow,
    health,
    knowledge,
    record,
    service,
    user,
)
from apps.scheduler.pool.pool import Pool
from apps.scheduler.scheduler.scheduler import Scheduler

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
app.include_router(appcenter.router)
app.include_router(service.router)
app.include_router(comment.router)
app.include_router(record.router)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(client.router)
app.include_router(blacklist.router)
app.include_router(document.router)
app.include_router(knowledge.router)
app.include_router(flow.router)
app.include_router(user.router)
# 初始化logger
logger = logging.getLogger("ray")
logger.setLevel(logging.INFO)
# 初始化后台定时任务
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(DeleteUserCron.delete_user, "cron", hour=3)

# 包装Ray
@serve.deployment(ray_actor_options={"num_gpus": 0})
@serve.ingress(app)
class FastAPIWrapper:
    """FastAPI Ray包装器"""


# 运行
if __name__ == "__main__":
    # 初始化Ray
    ray.init(dashboard_host="0.0.0.0", num_cpus=4)  # noqa: S104

    # 初始化必要资源
    words_check = WordsCheck.options(name="words_check").remote()
    ray.get(words_check.init.remote())  # type: ignore[attr-type]
    task = Task.options(name="task").remote()
    pool_actor = Pool.options(name="pool").remote()
    ray.get(pool_actor.init.remote())   # type: ignore[attr-type]
    # 初始化Scheduler
    scheduler_sctors = [Scheduler.options(name=f"scheduler_{i}").remote() for i in range(SCHEDULER_REPLICAS)]

    # 启动FastAPI
    serve.start(http_options=HTTPOptions(host="0.0.0.0", port=8002))  # noqa: S104
    serve.run(FastAPIWrapper.bind(), blocking=True)
