# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""进程处理器"""

import asyncio
import logging
import multiprocessing
import multiprocessing.context
import os
import signal
from collections.abc import Callable
from typing import ClassVar

logger = logging.getLogger(__name__)
mp = multiprocessing.get_context("spawn")


class ProcessHandler:
    """进程处理器类"""

    tasks: ClassVar[dict[str, multiprocessing.context.SpawnProcess]] = {}
    """存储进程的字典"""
    lock = multiprocessing.Lock()
    """锁对象"""
    max_processes = max((os.cpu_count() or 1) // 2, 1)
    """最大进程数"""
    timeout = 5
    """超时时间"""
    @staticmethod
    def subprocess_target(target: Callable, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """子进程目标函数"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(target(*args, **kwargs))
        finally:
            # 等待所有pending tasks完成
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    @staticmethod
    def get_all_task_ids() -> list[str]:
        """获取所有任务ID"""
        acquired = False
        acquired = ProcessHandler.lock.acquire(timeout=ProcessHandler.timeout)
        if not acquired:
            logger.warning("[ProcessHandler] 获取任务ID时锁超时。")
            return []
        taks_ids = list(ProcessHandler.tasks.keys())
        ProcessHandler.lock.release()
        return taks_ids

    @staticmethod
    def add_task(task_id: str, target: Callable, *args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        """添加任务"""
        acquired = False
        acquired = ProcessHandler.lock.acquire(timeout=ProcessHandler.timeout)
        if not acquired:
            logger.warning("[ProcessHandler] 获取任务ID时锁超时。")
            return False
        logger.info("[ProcessHandler] 添加任务 %s", task_id)
        if len(ProcessHandler.tasks) >= ProcessHandler.max_processes:
            logger.warning("[ProcessHandler] 任务数量已达上限(%s)，请稍后再试。", ProcessHandler.max_processes)
            ProcessHandler.lock.release()
            return False
        try:
            if task_id not in ProcessHandler.tasks:
                process = mp.Process(
                    target=ProcessHandler.subprocess_target,
                    args=(target, *args),
                    kwargs=kwargs,
                )
                ProcessHandler.tasks[task_id] = process
                process.start()
            else:
                logger.warning("[ProcessHandler] 任务ID %s 已存在，无法添加。", task_id)
                return False
            logger.info("[ProcessHandler] 添加任务成功 %s", task_id)
        except Exception:
            logger.exception("[ProcessHandler] 添加任务 %s 时发生异常", task_id)
            return False
        else:
            return True
        finally:
            if acquired:
                ProcessHandler.lock.release()

    @staticmethod
    def remove_task(task_id: str) -> None:
        """删除任务"""
        acquired = False
        acquired = ProcessHandler.lock.acquire(timeout=ProcessHandler.timeout)
        if not acquired:
            logger.warning("[ProcessHandler] 获取任务ID时锁超时。")
            return
        if task_id not in ProcessHandler.tasks:
            ProcessHandler.lock.release()
            logger.warning("[ProcessHandler] 任务ID %s 不存在，无法删除。", task_id)
            return
        process = ProcessHandler.tasks[task_id]
        del ProcessHandler.tasks[task_id]
        logger.info("[ProcessHandler] 任务ID %s 被删除。", task_id)
        try:
            pid = process.pid if process.is_alive() else None
            if pid is not None:
                os.kill(pid, signal.SIGKILL)  # type: ignore[arg-type]
                logger.info("[ProcessHandler] 进程 %s (%s) 被杀死。", task_id, pid)
            else:
                process.close()
        finally:
            if acquired:
                ProcessHandler.lock.release()
