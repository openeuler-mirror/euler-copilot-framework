# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""评论 Manager"""

import logging

from apps.common.mongo import MongoDB
from apps.schemas.record import RecordComment

logger = logging.getLogger(__name__)


class CommentManager:
    """评论相关操作"""

    @staticmethod
    async def query_comment(group_id: str, record_id: str) -> RecordComment | None:
        """
        根据问答ID查询评论

        :param record_id: 问答ID
        :return: 评论内容
        """
        record_group_collection = MongoDB.get_collection("record_group")
        result = await record_group_collection.aggregate(
            [
                {"$match": {"_id": group_id, "records.id": record_id}},
                {"$unwind": "$records"},
                {"$match": {"records.id": record_id}},
                {"$limit": 1},
            ],
        )
        result = await result.to_list(length=1)
        if result:
            return RecordComment.model_validate(result[0]["records"]["comment"])
        return None

    @staticmethod
    async def update_comment(group_id: str, record_id: str, data: RecordComment) -> None:
        """
        更新评论

        :param record_id: 问答ID
        :param data: 评论内容
        """
        record_group_collection = MongoDB.get_collection("record_group")
        await record_group_collection.update_one(
            {"_id": group_id, "records.id": record_id},
            {"$set": {"records.$.comment": data.model_dump(by_alias=True)}},
        )
