# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
import logging

from apps.models.mysql import Comment, MysqlDB
from apps.entities.comment import CommentData


class CommentManager:
    logger = logging.getLogger('gunicorn.error')

    @staticmethod
    def query_comment(record_id: str):
        result = None
        try:
            with MysqlDB().get_session() as session:
                result = session.query(Comment).filter(
                    Comment.record_id == record_id).first()
        except Exception as e:
            CommentManager.logger.info(
                f"Query comment failed due to error: {e}")
        return result

    @staticmethod
    def add_comment(user_sub: str, data: CommentData):
        try:
            with MysqlDB().get_session() as session:
                add_comment = Comment(user_sub=user_sub, record_id=data.record_id,
                                      is_like=data.is_like, dislike_reason=data.dislike_reason,
                                      reason_link=data.reason_link, reason_description=data.reason_description)
                session.add(add_comment)
                session.commit()
        except Exception as e:
            CommentManager.logger.info(
                f"Add comment failed due to error: {e}")

    @staticmethod
    def update_comment(user_sub: str, data: CommentData):
        try:
            with MysqlDB().get_session() as session:
                session.query(Comment).filter(Comment.user_sub == user_sub).filter(
                    Comment.record_id == data.record_id).update(
                    {"is_like": data.is_like, "dislike_reason": data.dislike_reason, "reason_link": data.reason_link,
                     "reason_description": data.reason_description})
                session.commit()
        except Exception as e:
            CommentManager.logger.info(
                f"Add comment failed due to error: {e}")

    @staticmethod
    def delete_comment_by_user_sub(user_sub: str):
        try:
            with MysqlDB().get_session() as session:
                session.query(Comment).filter(
                    Comment.user_sub == user_sub).delete()
                session.commit()
        except Exception as e:
            CommentManager.logger.info(
                f"delete comment by user_sub failed due to error: {e}")
