"""评论 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import logging
from typing import Optional

from apps.entities.collection import RecordComment
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)

class CommentManager:
    """评论相关操作"""

    @staticmethod
    async def query_comment(group_id: str, record_id: str) -> Optional[RecordComment]:
        """根据问答ID查询评论

        :param record_id: 问答ID
        :return: 评论内容
        """
        try:
            record_group_collection = MongoDB.get_collection("record_group")
            result = await record_group_collection.aggregate([
                {"$match": {"_id": group_id, "records._id": record_id}},
                {"$unwind": "$records"},
                {"$match": {"records._id": record_id}},
                {"$limit": 1},
            ])
            result = await result.to_list(length=1)
            if result:
                return RecordComment.model_validate(result[0]["records"]["comment"])
        except Exception:
            logger.exception("[CommentManager] 查询反馈失败")
        return None

    @staticmethod
    async def update_comment(group_id: str, record_id: str, data: RecordComment) -> bool:
        """更新评论

        :param record_id: 问答ID
        :param data: 评论内容
        :return: 是否更新成功；True/False
        """
        try:
            record_group_collection = MongoDB.get_collection("record_group")
            await record_group_collection.update_one({"_id": group_id, "records._id": record_id}, {"$set": {"records.$.comment": data.model_dump(by_alias=True)}})
            return True
        except Exception:
            logger.exception("[CommentManager] 更新反馈失败")
            return False
