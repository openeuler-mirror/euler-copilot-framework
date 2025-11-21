# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""工具类Mixin"""

import asyncio
import logging
import uuid

from apps.models import ExecutorStatus
from apps.schemas.request_data import RequestData
from apps.schemas.task import TaskData
from apps.services.activity import Activity
from apps.services.conversation import ConversationManager

_logger = logging.getLogger(__name__)


class UtilMixin:
    """通用工具方法的Mixin类"""

    task: TaskData
    post_body: RequestData

    async def _determine_app_id(self) -> uuid.UUID | None:
        """确定最终使用的 app_id"""
        conversation = None

        if self.task.metadata.conversationId:
            conversation = await ConversationManager.get_conversation_by_conversation_id(
                self.task.metadata.userId,
                self.task.metadata.conversationId,
            )

        if conversation and conversation.appId:
            final_app_id = conversation.appId
            _logger.info("[Scheduler] 使用Conversation中的appId: %s", final_app_id)

            if self.post_body.app and self.post_body.app.app_id and self.post_body.app.app_id != conversation.appId:
                _logger.warning(
                    "[Scheduler] post_body中的app_id(%s)与Conversation中的appId(%s)不符，忽略post_body中的app信息",
                    self.post_body.app.app_id,
                    conversation.appId,
                )
                self.post_body.app.app_id = conversation.appId
        elif self.post_body.app and self.post_body.app.app_id:
            final_app_id = self.post_body.app.app_id
            _logger.info("[Scheduler] Conversation中无appId，使用post_body中的app_id: %s", final_app_id)
        else:
            final_app_id = None
            _logger.info("[Scheduler] Conversation和post_body中均无appId，fallback到智能问答")

        return final_app_id

    async def _monitor_activity(self, kill_event: asyncio.Event, user_id: str) -> None:
        """监控用户活动状态，不活跃时终止工作流"""
        try:
            check_interval = 0.5

            while not kill_event.is_set():
                is_active = await Activity.is_active(user_id)

                if not is_active:
                    _logger.warning("[Scheduler] 用户 %s 不活跃，终止工作流", user_id)
                    kill_event.set()
                    break

                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            _logger.info("[Scheduler] 活动监控任务已取消")
        except Exception:
            _logger.exception("[Scheduler] 活动监控过程中发生错误")
            kill_event.set()

    async def _check_and_handle_executor_result(self) -> None:
        """检查并处理executor执行结果"""
        if not self.task.runtime.fullAnswer or self.task.runtime.fullAnswer.strip() == "":
            _logger.warning("[Scheduler] fullAnswer为空，设置executor状态为ERROR")
            if self.task.state:
                self.task.state.executorStatus = ExecutorStatus.ERROR
                if not self.task.state.errorMessage:
                    self.task.state.errorMessage = {
                        "err_msg": "执行完成但未生成任何答案",
                        "data": {},
                    }

        if self.task.state and self.task.state.executorStatus == ExecutorStatus.ERROR:
            error_msg = "Executor执行失败"
            if self.task.state.errorMessage:
                error_msg = f"Executor执行失败: {self.task.state.errorMessage.get('err_msg', '未知错误')}"
            _logger.error("[Scheduler] %s", error_msg)
            raise RuntimeError(error_msg)

        _logger.info("[Scheduler] Executor执行成功")
