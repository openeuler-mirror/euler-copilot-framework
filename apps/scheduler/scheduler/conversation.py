# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对话管理相关的Mixin类"""

import logging
import uuid

from apps.models import Conversation
from apps.services.appcenter import AppCenterManager
from apps.services.conversation import ConversationManager

_logger = logging.getLogger(__name__)


class ConversationMixin:
    """处理对话管理相关的逻辑"""

    async def create_new_conversation(
        self, title: str, user_id: str, app_id: uuid.UUID | None = None,
        *,
        debug: bool = False,
    ) -> Conversation:
        """判断并创建新对话"""
        if app_id and not await AppCenterManager.validate_user_app_access(user_id, app_id):
            err = "Invalid app_id."
            raise RuntimeError(err)
        new_conv = await ConversationManager.add_conversation_by_user(
            title=title,
            user_id=user_id,
            app_id=app_id,
            debug=debug,
        )
        if not new_conv:
            err = "Create new conversation failed."
            raise RuntimeError(err)
        return new_conv
