"""YAML 文件格式数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class OpenAPIInfo(BaseModel):
    """OpenAPI文件信息"""

    title: str = Field(..., description="API的标题")
    version: str = Field(..., description="API的版本")
    description: str = Field(..., description="API的描述")


class OpenAPIServer(BaseModel):
    """OpenAPI服务器信息"""

    url: str = Field(..., description="API的服务器地址")


class OpenAPITag(BaseModel):
    """OpenAPI标签定义"""

    name: str = Field(..., description="标签名称")
    description: Optional[str] = Field(None, description="标签描述")


class OpenAPIOperation(BaseModel):
    """OpenAPI操作定义，例如 GET、POST 等操作"""

    summary: Optional[str] = Field(None, description="操作摘要")
    description: Optional[str] = Field(None, description="操作描述")
    operation_id: Optional[str] = Field(None, description="操作唯一标识", alias="operationId")
    parameters: Optional[list[Any]] = Field(default_factory=list, description="参数列表")
    responses: dict[str, Any] = Field(..., description="响应定义")
    tags: Optional[list[str]] = Field(default_factory=list, description="标签列表")


class OpenAPIPath(BaseModel):
    """OpenAPI路径下不同 HTTP 方法的操作定义"""

    get: Optional[OpenAPIOperation] = Field(None, description="GET操作")
    put: Optional[OpenAPIOperation] = Field(None, description="PUT操作")
    post: Optional[OpenAPIOperation] = Field(None, description="POST操作")
    delete: Optional[OpenAPIOperation] = Field(None, description="DELETE操作")
    patch: Optional[OpenAPIOperation] = Field(None, description="PATCH操作")
    options: Optional[OpenAPIOperation] = Field(None, description="OPTIONS操作")
    head: Optional[OpenAPIOperation] = Field(None, description="HEAD操作")


class OpenAPISecurityScheme(BaseModel):
    """OpenAPI安全方案定义"""

    type: str = Field(..., description="安全方案类型，例如 apiKey、http、oauth2 等")
    description: Optional[str] = Field(None, description="安全方案描述")
    name: Optional[str] = Field(None, description="安全方案名称")
    in_: Optional[str] = Field(None, alias="in", description="安全方案传递位置，如 header、query 等")


class OpenAPIComponents(BaseModel):
    """OpenAPI组件定义"""

    schemas: Optional[dict[str, Any]] = Field(default_factory=dict, description="数据模型定义")
    parameters: Optional[dict[str, Any]] = Field(default_factory=dict, description="参数定义")
    security_schemes: Optional[dict[str, OpenAPISecurityScheme]] = Field(
        alias="securitySchemes",
        default_factory=dict,
        description="安全方案定义",
    )


class OpenAPI(BaseModel):
    """完整的 OpenAPI 文件格式数据结构"""

    openapi: str = Field(..., description="OpenAPI版本")
    info: OpenAPIInfo = Field(..., description="API的基本信息")
    servers: list[OpenAPIServer] = Field(..., description="API的服务器地址", min_length=1)
    paths: dict[str, OpenAPIPath] = Field(..., description="API的路径定义")
    components: Optional[OpenAPIComponents] = Field(None, description="API的组件定义")
    security: Optional[list[dict[str, list[str]]]] = Field(None, description="API的安全定义")
    tags: Optional[list[OpenAPITag]] = Field(None, description="API的标签定义")
