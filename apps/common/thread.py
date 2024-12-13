# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from concurrent.futures import ThreadPoolExecutor

from apps.common.singleton import Singleton

class ProcessThreadPool(metaclass=Singleton):
    """
    给每个进程分配一个线程池
    """

    thread_executor: ThreadPoolExecutor

    def __init__(self, thread_worker_num: int = 5):
        self.thread_executor = ThreadPoolExecutor(max_workers=thread_worker_num)

    def exec(self):
        """
        获取线程执行器
        :return: 线程执行器对象；可将任务提交到线程池中
        """
        return self.thread_executor
