"""任务模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

import ray

from apps.entities.enum_var import StepStatus
from apps.entities.record import (
    RecordContent,
    RecordData,
    RecordMetadata,
)
from apps.entities.request_data import RequestData
from apps.entities.task import TaskBlock, TaskData
from apps.manager.task import TaskManager
from apps.models.mongo import MongoDB


@ray.remote
class Task:
    """保存任务信息；每一个任务关联一组队列（现阶段只有输入和输出）"""

    def __init__(self) -> None:
        """初始化TaskManager"""
        self._task_map: dict[str, TaskBlock] = {}


    async def update_token_summary(self, task_id: str, input_num: int, output_num: int) -> None:
        """更新对应task_id的Token统计数据"""
        self._task_map[task_id].record.metadata.input_tokens += input_num
        self._task_map[task_id].record.metadata.output_tokens += output_num


    async def get_task(self, task_id: Optional[str] = None, session_id: Optional[str] = None, post_body: Optional[RequestData] = None) -> TaskBlock:
        """获取任务块"""
        # 如果task_map里面已经有了，则直接返回副本
        if task_id in self._task_map:
            return deepcopy(self._task_map[task_id])

        # 如果task_map里面没有，则尝试从数据库中读取
        if not session_id or not post_body:
            err = "session_id and conversation_id or group_id and conversation_id are required to recover/create a task."
            raise ValueError(err)

        if post_body.group_id:
            task = await TaskManager.get_task_by_group_id(post_body.group_id, post_body.conversation_id)
        else:
            task = await TaskManager.get_task_by_conversation_id(post_body.conversation_id)

        # 创建新的Record，缺失的数据延迟关联
        new_record = RecordData(
            id=str(uuid.uuid4()),
            conversationId=post_body.conversation_id,
            groupId=str(uuid.uuid4()) if not post_body.group_id else post_body.group_id,
            taskId="",
            content=RecordContent(
                question=post_body.question,
                answer="",
            ),
            metadata=RecordMetadata(
                input_tokens=0,
                output_tokens=0,
                time=0,
                feature=post_body.features.model_dump(by_alias=True),
            ),
            createdAt=round(datetime.now(timezone.utc).timestamp(), 3),
        )

        if not task:
            # 任务不存在，新建Task，并放入task_map
            task_id = str(uuid.uuid4())
            new_record.task_id = task_id

            self._task_map[task_id] = TaskBlock(
                session_id=session_id,
                record=new_record,
            )
            return deepcopy(self._task_map[task_id])

        # 任务存在，整理Task，放入task_map
        task_id = task.id
        new_record.task_id = task_id
        self._task_map[task_id] = TaskBlock(
            session_id=session_id,
            record=new_record,
            flow_state=task.state,
        )

        return deepcopy(self._task_map[task_id])

    async def set_task(self, task_id: str, value: TaskBlock) -> None:
        """设置任务块"""
        # 检查task_id合法性
        if task_id not in self._task_map:
            err = f"Task {task_id} not found"
            raise KeyError(err)

        # 替换task_map中的数据
        self._task_map[task_id] = value

    async def save_task(self, task_id: str) -> None:
        """保存任务块"""
        # 整理任务信息
        origin_task = await TaskManager.get_task_by_conversation_id(self._task_map[task_id].record.conversation_id)
        if not origin_task:
            # 创建新的Task记录
            task = TaskData(
                _id=task_id,
                conversation_id=self._task_map[task_id].record.conversation_id,
                record_groups=[self._task_map[task_id].record.group_id],
                state=self._task_map[task_id].flow_state,
                ended=False,
                updated_at=round(datetime.now(timezone.utc).timestamp(), 3),
            )
        else:
            # 更新已有的Task记录
            task = origin_task
            task.record_groups.append(self._task_map[task_id].record.group_id)
            task.state = self._task_map[task_id].flow_state
            task.updated_at = round(datetime.now(timezone.utc).timestamp(), 3)

        # 判断Task是否结束
        if (
            not self._task_map[task_id].flow_state or
            self._task_map[task_id].flow_state.status == StepStatus.ERROR or     # type: ignore[]
            self._task_map[task_id].flow_state.status == StepStatus.SUCCESS     # type: ignore[]
        ):
            task.ended = True

        # 使用MongoDB保存任务块
        task_collection = MongoDB.get_collection("task")

        if task_id not in self._task_map:
            err = f"Task {task_id} not found"
            raise ValueError(err)

        await task_collection.update_one({"_id": task_id}, {"$set": task.model_dump(by_alias=True, exclude_none=True)}, upsert=True)

        # 从task_map中删除任务块，释放内存
        del self._task_map[task_id]
