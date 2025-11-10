# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""评论 Manager"""

import logging
import uuid

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.models import Comment
from apps.schemas.record import RecordComment

logger = logging.getLogger(__name__)


class CommentManager:
    """评论相关操作"""

    @staticmethod
    async def query_comment(record_id: str) -> RecordComment | None:
        """
        根据问答ID查询评论

        :param record_id: 问答ID
        :return: 评论内容
        """
        async with postgres.session() as session:
            result = (
                await session.scalars(
                    select(Comment).where(Comment.recordId == uuid.UUID(record_id)),
                )
            ).one_or_none()
            if result:
                return RecordComment(
                    comment=result.commentType,
                    dislike_reason=result.feedbackType,
                    reason_link=result.feedbackLink,
                    reason_description=result.feedbackContent,
                    feedback_time=round(result.createdAt.timestamp(), 3),
                )
            return None

    @staticmethod
    async def update_comment(record_id: str, data: RecordComment, user_id: str) -> None:
        """
        更新评论

        :param record_id: 问答ID
        :param data: 评论内容
        """
        async with postgres.session() as session:
            result = (
                await session.scalars(
                    select(Comment).where(Comment.recordId == uuid.UUID(record_id)),
                )
            ).one_or_none()
            if result:
                result.commentType = data.comment
                result.feedbackType = data.feedback_type
                result.feedbackLink = data.feedback_link
                result.feedbackContent = data.feedback_content
            else:
                comment_info = Comment(
                    recordId=uuid.UUID(record_id),
                    userId=user_id,
                    commentType=data.comment,
                    feedbackType=data.feedback_type,
                    feedbackLink=data.feedback_link,
                    feedbackContent=data.feedback_content,
                )
                session.add(comment_info)
            await session.commit()
