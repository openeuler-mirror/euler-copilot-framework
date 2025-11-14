# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户限流"""

import uuid
from datetime import UTC, datetime
import logging
from apps.common.mongo import MongoDB
from apps.constants import SLIDE_WINDOW_QUESTION_COUNT, SLIDE_WINDOW_TIME
from apps.exceptions import ActivityError

logger = logging.getLogger(__name__)


class Activity:
    """用户活动控制，限制单用户同一时间只能有SLIDE_WINDOW_QUESTION_COUNT个请求"""

    @staticmethod
    async def is_active(active_id: str) -> bool:
        """
        判断当前用户是否正在提问（占用GPU资源）

        :param user_sub: 用户实体ID
        :return: 判断结果，正在提问则返回True
        """

        # 检查用户是否正在提问
        active = await MongoDB.get_collection("activity").find_one(
            {"_id": active_id},
        )
        return bool(active)

    @staticmethod
    async def set_active(user_sub: str) -> str:
        """设置用户的活跃标识"""
        time = round(datetime.now(UTC).timestamp(), 3)
        # 设置用户活跃状态
        collection = MongoDB.get_collection("activity")
        # 查看用户活跃标识是否在滑动窗口内

        if await collection.count_documents({"user_sub": user_sub, "timestamp": {"$gt": time - SLIDE_WINDOW_TIME}}) >= SLIDE_WINDOW_QUESTION_COUNT:
            err = "[Activity] 用户在滑动窗口内提问次数超过限制，请稍后再试。"
            raise ActivityError(err)
        await collection.delete_many(
            {"user_sub": user_sub, "timestamp": {
                "$lte": time - SLIDE_WINDOW_TIME}},
        )
        # 插入新的活跃记录
        tmp_record = {
            "_id": str(uuid.uuid4()),
            "user_sub": user_sub,
            "timestamp": time,
        }
        await collection.insert_one(
            tmp_record
        )
        return tmp_record["_id"]

    @staticmethod
    async def remove_active(active_id: str) -> None:
        """
        清除用户的活跃标识，释放GPU资源

        :param user_sub: 用户实体ID
        """
        # 清除用户当前活动标识
        await MongoDB.get_collection("activity").delete_one(
            {"_id": active_id},
        )
