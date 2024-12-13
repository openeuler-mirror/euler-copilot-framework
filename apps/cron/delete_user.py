# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from datetime import datetime, timedelta, timezone

import pytz
import logging

from apps.manager.audit_log import AuditLogData, AuditLogManager
from apps.manager.comment import CommentManager
from apps.manager.record import RecordManager
from apps.manager.user import UserManager
from apps.manager.conversation import ConversationManager


class DeleteUserCron:
    logger = logging.getLogger('gunicorn.error')

    @staticmethod
    def delete_user():
        try:
            now = datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
            thirty_days_ago = now - timedelta(days=30)
            userinfos = UserManager.query_userinfo_by_login_time(
                thirty_days_ago)
            for user in userinfos:
                conversations = ConversationManager.get_conversation_by_user_sub(
                    user.user_sub)
                for conv in conversations:
                    RecordManager.delete_encrypted_qa_pair_by_conversation_id(
                        conv.conversation_id)
                CommentManager.delete_comment_by_user_sub(user.user_sub)
                UserManager.delete_userinfo_by_user_sub(user.user_sub)
                data = AuditLogData(method_type='internal_scheduler_job', source_name='delete_user', ip='internal',
                                    result=f'Deleted user: {user.user_sub}', reason='30天未登录')
                AuditLogManager.add_audit_log(user.user_sub, data)
        except Exception as e:
            DeleteUserCron.logger.info(
                f"Scheduler delete user failed: {e}")
