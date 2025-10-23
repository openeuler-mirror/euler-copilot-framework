# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 返回数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.models import LLMType

from .parameters import (
    BoolOperate,
    DictOperate,
    ListOperate,
    NumberOperate,
    StringOperate,
    Type,
)
from .record import RecordData
from .user import UserInfo


class ResponseData(BaseModel):
    """基础返回数据结构"""

    code: int
    message: str
    result: Any


class AuthUserMsg(BaseModel):
    """GET /api/auth/user Result数据结构"""

    user_sub: str
    revision: bool
    is_admin: bool
    auto_execute: bool


class AuthUserRsp(ResponseData):
    """GET /api/auth/user 返回数据结构"""

    result: AuthUserMsg


class HealthCheckRsp(BaseModel):
    """GET /health_check 返回数据结构"""

    status: str



class RecordListMsg(BaseModel):
    """GET /api/record/{conversation_id} Result数据结构"""

    records: list[RecordData]


class RecordListRsp(ResponseData):
    """GET /api/record/{conversation_id} 返回数据结构"""

    result: RecordListMsg



class OidcRedirectMsg(BaseModel):
    """GET /api/auth/redirect Result数据结构"""

    url: str


class OidcRedirectRsp(ResponseData):
    """GET /api/auth/redirect 返回数据结构"""

    result: OidcRedirectMsg


class ListTeamKnowledgeMsg(BaseModel):
    """GET /api/knowledge Result数据结构"""

    team_kb_list: list[uuid.UUID] = Field(default=[], alias="teamKbList", description="团队知识库列表")


class ListTeamKnowledgeRsp(ResponseData):
    """GET /api/knowledge 返回数据结构"""

    result: ListTeamKnowledgeMsg


class UserGetMsp(BaseModel):
    """GET /api/user result"""

    total: int = Field(default=0)
    user_info_list: list[UserInfo] = Field(alias="userInfoList", default=[])


class UserGetRsp(ResponseData):
    """GET /api/user 返回数据结构"""

    result: UserGetMsp


class LLMProviderInfo(BaseModel):
    """LLM数据结构"""

    llm_id: str = Field(alias="llmId", description="LLM ID")
    llm_description: str = Field(default="", alias="llmDescription", description="LLM描述")
    llm_type: list[LLMType] = Field(default=[], alias="llmType", description="LLM类型")
    model_name: str = Field(description="模型名称", alias="modelName")
    max_tokens: int | None = Field(default=None, description="最大token数", alias="maxTokens")


class ListLLMRsp(ResponseData):
    """GET /api/llm 返回数据结构"""

    result: list[LLMProviderInfo] = Field(default=[], title="Result")


class LLMAdminInfo(BaseModel):
    """LLM管理员视图数据结构"""

    llm_id: str = Field(alias="llmId", description="LLM ID")
    llm_description: str = Field(default="", alias="llmDescription", description="LLM描述")
    llm_type: list[LLMType] = Field(default=[], alias="llmType", description="LLM类型")
    base_url: str = Field(alias="baseUrl", description="API Base URL")
    api_key: str = Field(alias="apiKey", description="API Key")
    model_name: str = Field(alias="modelName", description="模型名称")
    max_tokens: int = Field(alias="maxTokens", description="最大token数")
    ctx_length: int = Field(alias="ctxLength", description="上下文长度")
    temperature: float = Field(default=0.7, description="温度")
    provider: str | None = Field(default=None, description="提供商")
    extra_config: dict[str, Any] = Field(default_factory=dict, alias="extraConfig", description="额外配置")


class ListLLMAdminRsp(ResponseData):
    """GET /api/llm/config 返回数据结构"""

    result: list[LLMAdminInfo] = Field(default=[], title="Result")


class ParamsNode(BaseModel):
    """参数数据结构"""

    param_name: str = Field(..., description="参数名称", alias="paramName")
    param_path: str = Field(..., description="参数路径", alias="paramPath")
    param_type: Type = Field(..., description="参数类型", alias="paramType")
    sub_params: list["ParamsNode"] | None = Field(
        default=None, description="子参数列表", alias="subParams",
    )


class StepParams(BaseModel):
    """参数数据结构"""

    step_id: uuid.UUID = Field(..., description="步骤ID", alias="stepId")
    name: str = Field(..., description="Step名称")
    params_node: ParamsNode | None = Field(
        default=None, description="参数节点", alias="paramsNode")


class GetParamsRsp(ResponseData):
    """GET /api/params 返回数据结构"""

    result: list[StepParams] = Field(
        default=[], description="参数列表", alias="result",
    )


class OperateAndBindType(BaseModel):
    """操作和绑定类型数据结构"""

    operate: NumberOperate | StringOperate | ListOperate | BoolOperate | DictOperate = Field(description="操作类型")
    bind_type: Type | None = Field(description="绑定类型")


class GetOperaRsp(ResponseData):
    """GET /api/operate 返回数据结构"""

    result: list[OperateAndBindType] = Field(..., title="Result")


class SelectedSpecialLlmID(BaseModel):
    """用户选择的LLM数据结构"""

    functionLLM: str | None = Field(default=None, description="函数模型ID")  # noqa: N815
    embeddingLLM: str | None = Field(default=None, description="向量模型ID")  # noqa: N815
