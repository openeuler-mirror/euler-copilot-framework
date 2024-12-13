# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import uuid
from datetime import datetime, timezone

import pytz
import logging

from apps.models.mysql import MysqlDB, Conversation


class ConversationManager:
    logger = logging.getLogger('gunicorn.error')

    @staticmethod
    def get_conversation_by_user_sub(user_sub):
        results = []
        try:
            with MysqlDB().get_session() as session:
                results = session.query(Conversation).filter(
                    Conversation.user_sub == user_sub).all()
        except Exception as e:
            ConversationManager.logger.info(
                f"Get conversation by user_sub failed: {e}")
        return results

    @staticmethod
    def get_conversation_by_conversation_id(conversation_id):
        result = None
        try:
            with MysqlDB().get_session() as session:
                result = session.query(Conversation).filter(
                    Conversation.conversation_id == conversation_id).first()
        except Exception as e:
            ConversationManager.logger.info(
                f"Get conversation by conversation_id failed: {e}")
        return result

    @staticmethod
    def add_conversation_by_user_sub(user_sub):
        conversation_id = str(uuid.uuid4().hex)
        try:
            with MysqlDB().get_session() as session:
                conv = Conversation(conversation_id=conversation_id,
                                       user_sub=user_sub, title="New Chat",
                                       created_time=datetime.now(timezone.utc).astimezone(
                                      pytz.timezone('Asia/Shanghai')
                                  ))
                session.add(conv)
                session.commit()
                session.refresh(conv)
        except Exception as e:
            conversation_id = None
            ConversationManager.logger.info(
                f"Add conversation by user_sub failed: {e}")
        return conversation_id

    @staticmethod
    def update_conversation_by_conversation_id(conversation_id, title):
        try:
            with MysqlDB().get_session() as session:
                session.query(Conversation).filter(Conversation.conversation_id ==
                                                   conversation_id).update({"title": title})
                session.commit()
        except Exception as e:
            ConversationManager.logger.info(
                f"Update conversation by conversation_id failed: {e}")
        result = ConversationManager.get_conversation_by_conversation_id(
            conversation_id)
        return result

    @staticmethod
    def update_conversation_metadata_by_conversation_id(conversation_id, title, created_time):
        try:
            with MysqlDB().get_session() as session:
                session.query(Conversation).filter(Conversation.conversation_id == conversation_id).update({
                    "title": title,
                    "created_time": created_time
                })
        except Exception as e:
            ConversationManager.logger.info(f"Update conversation metadata by conversation_id failed: {e}")
        result = ConversationManager.get_conversation_by_conversation_id(conversation_id)
        return result

    @staticmethod
    def delete_conversation_by_conversation_id(conversation_id):
        try:
            with MysqlDB().get_session() as session:
                session.query(Conversation).filter(Conversation.conversation_id == conversation_id).delete()
                session.commit()
        except Exception as e:
            ConversationManager.logger.info(
                f"Delete conversation by conversation_id failed: {e}")

    @staticmethod
    def delete_conversation_by_user_sub(user_sub):
        try:
            with MysqlDB().get_session() as session:
                session.query(Conversation).filter(
                    Conversation.user_sub == user_sub).delete()
                session.commit()
        except Exception as e:
            ConversationManager.logger.info(
                f"Delete conversation by user_sub failed: {e}")

    @staticmethod
    def update_summary(conversation_id, summary):
        try:
            with MysqlDB().get_session() as session:
                session.query(Conversation).filter(Conversation.conversation_id == conversation_id).update({
                    "summary": summary
                })
                session.commit()
        except Exception as e:
            ConversationManager.logger.info(f"Update summary failed: {e}")
