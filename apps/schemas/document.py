# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 返回数据结构 - 文档相关"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .enum_var import DocumentStatus


class BaseDocumentItem(BaseModel):
    """文档公共字段"""

    id: uuid.UUID = Field(description="文档ID")
    name: str = Field(default="", description="文档名称")
    type: str = Field(default="", description="文档类型")
    size: float = Field(default=0.0, description="文档大小")
    created_at: datetime | None = Field(default=None, description="创建时间")
    user_name: str | None = Field(default=None, description="上传者用户名")
    conversation_id: str | None = None

    class Config:
        """配置"""

        populate_by_name = True


class DocumentInfo(BaseModel):
    """RAG使用的文档信息"""

    id: uuid.UUID = Field(description="文档ID")
    order: int = Field(description="文档顺序")
    name: str = Field(default="", description="文档名称")
    author: str = Field(default="", description="文档作者")
    extension: str = Field(default="", description="文档扩展名")
    abstract: str = Field(default="", description="文档摘要")
    size: int = Field(default=0, description="文档大小")
    created_at: float = Field(description="创建时间")


class ConversationDocumentItem(BaseDocumentItem):
    """GET /api/document/{conversation_id} Result内元素数据结构"""

    status: DocumentStatus


class ConversationDocumentMsg(BaseModel):
    """GET /api/document/{conversation_id} Result数据结构"""

    documents: list[ConversationDocumentItem] = []


class ConversationDocumentRsp(BaseModel):
    """GET /api/document/{conversation_id} 返回数据结构"""

    code: int
    message: str
    result: ConversationDocumentMsg


class UploadDocumentMsg(BaseModel):
    """POST /api/document/{conversation_id} 返回数据结构"""

    documents: list[BaseDocumentItem]


class UploadDocumentRsp(BaseModel):
    """POST /api/document/{conversation_id} 返回数据结构"""

    code: int
    message: str
    result: UploadDocumentMsg
