# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""直接回复工具"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.reply.schema import DirectReplyInput, DirectReplyOutput
from apps.schemas.enum_var import CallOutputType, CallType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class DirectReply(CoreCall, input_model=DirectReplyInput, output_model=DirectReplyOutput):
    """直接回复工具，支持变量引用语法"""

    to_user: bool = Field(default=True)

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(
            name="直接回复", 
            type=CallType.DEFAULT,
            description="直接回复用户输入的内容，支持变量插入"
        )

    async def _init(self, call_vars: CallVars) -> DirectReplyInput:
        """初始化DirectReply工具"""
        answer = getattr(self, 'answer', '')
        return DirectReplyInput(answer=answer)

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行直接回复"""
        data = DirectReplyInput(**input_data)
        
        try:
            # 使用基类的变量解析功能处理文本中的变量引用
            final_answer = await self._resolve_variables_in_text(data.answer, self._sys_vars)
            
            logger.info(f"[DirectReply] 原始答案: {data.answer}")
            logger.info(f"[DirectReply] 解析后答案: {final_answer}")
            
            # 直接返回处理后的内容
            yield CallOutputChunk(
                type=CallOutputType.TEXT, 
                content=final_answer
            )
            
        except Exception as e:
            logger.error(f"[DirectReply] 处理回复内容失败: {e}")
            raise CallError(
                message=f"直接回复处理失败：{e!s}", 
                data={"original_answer": data.answer}
            ) from e
