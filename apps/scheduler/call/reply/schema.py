# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""DirectReply工具的输入输出定义"""

from pydantic import Field
from typing import Dict, Optional

from apps.scheduler.call.core import DataBase


class DirectReplyInput(DataBase):
    """定义DirectReply工具调用的输入"""

    answer: str = Field(description="直接回复的内容，支持变量引用语法")
    attachment: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None, 
        description="文件变量字典，key为变量名，value为变量详细信息 {'variableName': 'file', 'displayName': 'conversation.file', 'fileType': 'file'}"
    )


class DirectReplyOutput(DataBase):
    """定义DirectReply工具调用的输出"""

    message: str = Field(description="处理后的回复消息")
    attachments: Optional[dict] = Field(
        default=None, 
        description="附件字典，key为变量名，value为文件信息"
    ) 