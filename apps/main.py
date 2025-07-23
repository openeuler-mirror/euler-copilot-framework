"""
主程序

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import logging.config
import signal
import sys
from contextlib import asynccontextmanager

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
from apps.services.predecessor_cache_service import cleanup_background_tasks

# 全局变量用于跟踪后台任务
_cleanup_task = None

async def cleanup_on_shutdown():
    """应用关闭时的清理函数"""
    logger = logging.getLogger(__name__)
    logger.info("开始清理应用资源...")
    
    try:
        # 取消定期清理任务
        global _cleanup_task
        if _cleanup_task and not _cleanup_task.done():
            _cleanup_task.cancel()
            try:
                await _cleanup_task
            except asyncio.CancelledError:
                logger.info("定期清理任务已取消")
        
        # 清理后台任务
        await cleanup_background_tasks()
        
        # 关闭Redis连接
        from apps.common.redis_cache import RedisCache
        redis_cache = RedisCache()
        if redis_cache.is_connected():
            await redis_cache.close()
            logger.info("Redis连接已关闭")
            
    except Exception as e:
        logger.error(f"清理应用资源时出错: {e}")
    
    logger.info("应用资源清理完成")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化
    await init_resources()
    
    yield
    
    # 关闭时的清理
    await cleanup_on_shutdown()

# 定义FastAPI app
app = FastAPI(
    title="Euler Copilot Framework",
    description="AI-powered automation framework",
    version="1.0.0",
    lifespan=lifespan,
)
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


async def init_resources() -> None:
    """初始化必要资源"""
    WordsCheck()
    await LanceDB().init()
    await Pool.init()
    TokenCalculator()
    
    # 初始化变量池管理器
    from apps.scheduler.variable.pool_manager import initialize_pool_manager
    await initialize_pool_manager()
    
    # 初始化前置节点变量缓存服务
    try:
        from apps.services.predecessor_cache_service import PredecessorCacheService, periodic_cleanup_background_tasks
        await PredecessorCacheService.initialize_redis()
        
        # 启动定期清理任务
        global _cleanup_task
        _cleanup_task = asyncio.create_task(start_periodic_cleanup())
        
        logging.info("前置节点变量缓存服务初始化成功")
    except Exception as e:
        logging.warning(f"前置节点变量缓存服务初始化失败（将降级使用实时解析）: {e}")

async def start_periodic_cleanup():
    """启动定期清理任务"""
    try:
        from apps.services.predecessor_cache_service import periodic_cleanup_background_tasks
        while True:
            # 每60秒清理一次已完成的后台任务
            await asyncio.sleep(60)
            await periodic_cleanup_background_tasks()
    except asyncio.CancelledError:
        logging.info("定期清理任务已取消")
        raise  # 重新抛出CancelledError
    except Exception as e:
        logging.error(f"定期清理任务异常: {e}")

# 运行
if __name__ == "__main__":
    def signal_handler(signum, frame):
        """信号处理器"""
        logger = logging.getLogger(__name__)
        logger.info(f"收到信号 {signum}，准备关闭应用...")
        sys.exit(0)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info", log_config=None)
