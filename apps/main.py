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
    variable
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
app.include_router(variable.router)

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
    logger = logging.getLogger(__name__)
    
    WordsCheck()
    await LanceDB().init()
    await Pool.init()
    TokenCalculator()
    
    # 初始化变量池管理器
    from apps.scheduler.variable.pool_manager import initialize_pool_manager
    await initialize_pool_manager()
    
    # 🔑 新增：启动时清理遗留文件
    try:
        logger.info("开始启动时文件清理...")
        await startup_file_cleanup()
        logger.info("启动时文件清理完成")
    except Exception as e:
        logger.error(f"启动时文件清理失败: {e}")
    
    # 初始化前置节点变量缓存服务
    try:
        from apps.services.predecessor_cache_service import PredecessorCacheService, periodic_cleanup_background_tasks
        await PredecessorCacheService.initialize_redis()
        
        # 项目启动时清空所有前置节点缓存，确保使用最新的算法逻辑
        await PredecessorCacheService.clear_all_predecessor_cache()
        
        # 启动定期清理任务
        global _cleanup_task
        _cleanup_task = asyncio.create_task(start_periodic_cleanup())
        
        logging.info("前置节点变量缓存服务初始化成功")
    except Exception as e:
        logging.warning(f"前置节点变量缓存服务初始化失败（将降级使用实时解析）: {e}")


async def startup_file_cleanup():
    """启动时清理遗留文件（除了已绑定历史记录的文件）"""
    logger = logging.getLogger(__name__)
    try:
        from apps.services.document import DocumentManager
        from apps.scheduler.variable.type import VariableType
        from apps.common.mongo import MongoDB
        
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        variables_collection = mongo.get_collection("variables")
        record_group_collection = mongo.get_collection("record_group")
        conversation_collection = mongo.get_collection("conversation")
        
        # 获取所有文档ID
        all_file_ids = set()
        async for doc in doc_collection.find({}, {"_id": 1}):
            all_file_ids.add(doc["_id"])
        
        # 获取已绑定历史记录的文件ID
        protected_file_ids = set()
        async for record_group in record_group_collection.find({}, {"docs": 1}):
            docs = record_group.get("docs", [])
            for doc in docs:
                doc_id = doc.get("id") or doc.get("_id")
                if doc_id:
                    protected_file_ids.add(doc_id)
        
        # 获取conversation中unused_docs的文件ID（这些是暂时的，不应清理）
        unused_file_ids = set()
        async for conv in conversation_collection.find({}, {"unused_docs": 1}):
            unused_docs = conv.get("unused_docs", [])
            unused_file_ids.update(unused_docs)
        
        # 获取变量中引用的文件ID
        variable_file_ids = set()
        async for var_doc in variables_collection.find({
            "metadata.var_type": {"$in": [VariableType.FILE.value, VariableType.ARRAY_FILE.value]}
        }):
            try:
                value = var_doc.get("value", {})
                if isinstance(value, dict):
                    var_type = var_doc.get("metadata", {}).get("var_type")
                    if var_type == VariableType.FILE.value:
                        file_id = value.get("file_id")
                        if file_id:
                            variable_file_ids.add(file_id)
                    elif var_type == VariableType.ARRAY_FILE.value:
                        file_ids = value.get("file_ids", [])
                        variable_file_ids.update(file_ids)
            except Exception as e:
                logger.warning(f"解析变量文件引用失败: {e}")
        
        # 计算可以清理的文件：不在历史记录、不在unused_docs、不在变量中引用的
        protected_ids = protected_file_ids | unused_file_ids | variable_file_ids
        orphaned_file_ids = all_file_ids - protected_ids
        
        if orphaned_file_ids:
            logger.info(f"启动时发现 {len(orphaned_file_ids)} 个遗留文件，开始清理")
            
            # 批量删除遗留文件
            cleaned_count = 0
            for file_id in orphaned_file_ids:
                try:
                    # 从document表获取文件信息以确定所有者
                    doc_info = await doc_collection.find_one({"_id": file_id})
                    if doc_info:
                        user_sub = doc_info.get("user_sub")
                        if user_sub:
                            await DocumentManager.delete_document(user_sub, [file_id])
                            cleaned_count += 1
                        else:
                            logger.warning(f"遗留文件 {file_id} 缺少user_sub信息")
                except Exception as e:
                    logger.error(f"删除遗留文件 {file_id} 失败: {e}")
            
            logger.info(f"启动时清理了 {cleaned_count} 个遗留文件")
        else:
            logger.info("启动时未发现遗留文件")
            
    except Exception as e:
        logger.error(f"启动时文件清理失败: {e}")


async def cleanup_orphaned_files():
    """清理孤儿文件（不被任何变量引用且未绑定历史记录的文件）"""
    logger = logging.getLogger(__name__)
    try:
        from apps.services.document import DocumentManager
        from apps.scheduler.variable.type import VariableType
        from apps.common.mongo import MongoDB
        
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        variables_collection = mongo.get_collection("variables")
        record_group_collection = mongo.get_collection("record_group")
        conversation_collection = mongo.get_collection("conversation")
        
        # 获取所有文档ID
        all_file_ids = set()
        async for doc in doc_collection.find({}, {"_id": 1}):
            all_file_ids.add(doc["_id"])
        
        # 🔑 修正：获取已绑定历史记录的文件ID（这些是受保护的）
        protected_file_ids = set()
        async for record_group in record_group_collection.find({}, {"docs": 1}):
            docs = record_group.get("docs", [])
            for doc in docs:
                doc_id = doc.get("id") or doc.get("_id")
                if doc_id:
                    protected_file_ids.add(doc_id)
        
        # 获取conversation中unused_docs的文件ID（这些也要保护）
        unused_file_ids = set()
        async for conv in conversation_collection.find({}, {"unused_docs": 1}):
            unused_docs = conv.get("unused_docs", [])
            unused_file_ids.update(unused_docs)
        
        # 获取所有变量中引用的文件ID
        referenced_file_ids = set()
        async for var_doc in variables_collection.find({
            "metadata.var_type": {"$in": [VariableType.FILE.value, VariableType.ARRAY_FILE.value]}
        }):
            try:
                value = var_doc.get("value", {})
                if isinstance(value, dict):
                    var_type = var_doc.get("metadata", {}).get("var_type")
                    if var_type == VariableType.FILE.value:
                        file_id = value.get("file_id")
                        if file_id:
                            referenced_file_ids.add(file_id)
                    elif var_type == VariableType.ARRAY_FILE.value:
                        file_ids = value.get("file_ids", [])
                        referenced_file_ids.update(file_ids)
            except Exception as e:
                logger.warning(f"解析变量文件引用失败: {e}")
        
        # 找出孤儿文件：既不在历史记录中，也不在unused_docs中，也不被变量引用
        protected_ids = protected_file_ids | unused_file_ids | referenced_file_ids
        orphaned_file_ids = all_file_ids - protected_ids
        
        if orphaned_file_ids:
            logger.info(f"发现 {len(orphaned_file_ids)} 个孤儿文件，开始清理")
            
            # 批量删除孤儿文件
            cleaned_count = 0
            for file_id in orphaned_file_ids:
                try:
                    # 从document表获取文件信息以确定所有者
                    doc_info = await doc_collection.find_one({"_id": file_id})
                    if doc_info:
                        user_sub = doc_info.get("user_sub")
                        if user_sub:
                            await DocumentManager.delete_document(user_sub, [file_id])
                            cleaned_count += 1
                        else:
                            logger.warning(f"孤儿文件 {file_id} 缺少user_sub信息")
                except Exception as e:
                    logger.error(f"删除孤儿文件 {file_id} 失败: {e}")
            
            logger.info(f"孤儿文件清理完成，共清理 {cleaned_count} 个文件")
        else:
            logger.debug("未发现孤儿文件")
            
    except Exception as e:
        logger.error(f"孤儿文件清理失败: {e}")

async def start_periodic_cleanup():
    """启动定期清理任务"""
    import asyncio
    from apps.scheduler.variable.pool_manager import get_pool_manager
    from apps.common.mongo import MongoDB
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    
    async def cleanup_task():
        """定期清理任务"""
        while True:
            try:
                # 每30分钟执行一次清理
                await asyncio.sleep(30 * 60)
                
                logger.info("开始定期清理任务")
                
                # 获取活跃的对话列表
                mongo = MongoDB()
                conv_collection = mongo.get_collection("conversation")
                
                # 获取最近24小时内有活动的对话ID
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                active_conversations = set()
                
                async for conv in conv_collection.find(
                    {"updated_at": {"$gte": cutoff_time}}, 
                    {"_id": 1}
                ):
                    active_conversations.add(conv["_id"])
                
                # 清理未使用的对话变量池（现在包含文件清理）
                pool_manager = await get_pool_manager()
                await pool_manager.cleanup_unused_pools(active_conversations)
                
                # 🔑 新增：清理孤儿文件（在document表中存在但不被任何变量引用的文件）
                await cleanup_orphaned_files()
                
                logger.info("定期清理任务完成")
                
            except Exception as e:
                logger.error(f"定期清理任务失败: {e}")
    
    # 启动后台任务
    asyncio.create_task(cleanup_task())

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
