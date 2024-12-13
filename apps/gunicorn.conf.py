# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from apps.common.thread import ProcessThreadPool
from apps.common.wordscheck import WordsCheck
from apps.scheduler.pool.loader import Loader


preload_app = True
bind = "0.0.0.0:8002"
workers = 8
timeout = 300
accesslog = "-"
capture_output = True
worker_class = "uvicorn.workers.UvicornWorker"

def on_starting(server):
    """
    Gunicorn服务器启动时的初始化代码
    :param server: 服务器配置项
    :return:
    """
    WordsCheck.init()
    Loader.init()


def post_fork(server, worker):
    """
    Gunicorn服务器每个Worker进程启动后的初始化代码
    :param server: 服务器配置项
    :param worker: Worker配置项
    :return:
    """
    ProcessThreadPool(thread_worker_num=5)
