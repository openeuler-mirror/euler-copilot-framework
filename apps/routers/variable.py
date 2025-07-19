# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 变量管理 API"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.dependency import get_user
from apps.dependency.user import verify_user
from apps.scheduler.variable.pool import get_variable_pool
from apps.scheduler.variable.type import VariableType, VariableScope
from apps.scheduler.variable.parser import VariableParser
from apps.schemas.response_data import ResponseData

router = APIRouter(
    prefix="/api/variable",
    tags=["variable"],
    dependencies=[
        Depends(verify_user),
    ],
)


# 请求和响应模型
class CreateVariableRequest(BaseModel):
    """创建变量请求"""
    name: str = Field(description="变量名称")
    var_type: VariableType = Field(description="变量类型")
    scope: VariableScope = Field(description="变量作用域")
    value: Optional[str] = Field(default=None, description="变量值")
    description: Optional[str] = Field(default=None, description="变量描述")
    flow_id: Optional[str] = Field(default=None, description="流程ID（环境级和对话级变量必需）")


class UpdateVariableRequest(BaseModel):
    """更新变量请求"""
    value: str = Field(description="新的变量值")


class VariableResponse(BaseModel):
    """变量响应"""
    name: str = Field(description="变量名称")
    var_type: str = Field(description="变量类型")
    scope: str = Field(description="变量作用域")
    value: str = Field(description="变量值")
    description: Optional[str] = Field(description="变量描述")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class VariableListResponse(BaseModel):
    """变量列表响应"""
    variables: List[VariableResponse] = Field(description="变量列表")
    total: int = Field(description="总数量")


class ParseTemplateRequest(BaseModel):
    """解析模板请求"""
    template: str = Field(description="包含变量引用的模板")
    flow_id: Optional[str] = Field(default=None, description="流程ID")


class ParseTemplateResponse(BaseModel):
    """解析模板响应"""
    parsed_template: str = Field(description="解析后的模板")
    variables_used: List[str] = Field(description="使用的变量引用")


class ValidateTemplateResponse(BaseModel):
    """验证模板响应"""
    is_valid: bool = Field(description="是否有效")
    invalid_references: List[str] = Field(description="无效的变量引用")


@router.post(
    "/create",
    responses={
        status.HTTP_200_OK: {"model": ResponseData},
        status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
    },
)
async def create_variable(
    user_sub: Annotated[str, Depends(get_user)],
    request: CreateVariableRequest = Body(...),
) -> ResponseData:
    """创建变量"""
    try:
        # 验证作用域权限
        if request.scope == VariableScope.SYSTEM:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="不允许创建系统级变量"
            )
        
        pool = await get_variable_pool()
        
        # 创建变量
        variable = await pool.add_variable(
            name=request.name,
            var_type=request.var_type,
            scope=request.scope,
            value=request.value,
            description=request.description,
            user_sub=None,  # 不再支持用户级变量
            flow_id=request.flow_id if request.scope in [VariableScope.ENVIRONMENT, VariableScope.CONVERSATION] else None,
            conversation_id=None,  # 不再使用conversation_id，统一使用flow_id
        )
        
        return ResponseData(
            code=200,
            message="变量创建ß功",
            result={"variable_name": variable.name},
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建变量失败: {str(e)}"
        )


@router.put(
    "/update",
    responses={
        status.HTTP_200_OK: {"model": ResponseData},
        status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def update_variable(
    user_sub: Annotated[str, Depends(get_user)],
    name: str = Query(..., description="变量名称"),
    scope: VariableScope = Query(..., description="变量作用域"),
    flow_id: Optional[str] = Query(default=None, description="流程ID（环境级和对话级变量必需）"),
    request: UpdateVariableRequest = Body(...),
) -> ResponseData:
    """更新变量值"""
    try:
        pool = await get_variable_pool()
        
        # 更新变量
        variable = await pool.update_variable(
            name=name,
            scope=scope,
            value=request.value,
            user_sub=None,  # 不再支持用户级变量
            flow_id=flow_id,
            conversation_id=None,  # 不再使用conversation_id
        )
        
        return ResponseData(
            code=200,
            message="变量更新成功",
            result={"variable_name": variable.name}
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新变量失败: {str(e)}"
        )


@router.delete(
    "/delete",
    responses={
        status.HTTP_200_OK: {"model": ResponseData},
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def delete_variable(
    user_sub: Annotated[str, Depends(get_user)],
    name: str = Query(..., description="变量名称"),
    scope: VariableScope = Query(..., description="变量作用域"),
    flow_id: Optional[str] = Query(default=None, description="流程ID（环境级和对话级变量必需）"),
) -> ResponseData:
    """删除变量"""
    try:
        pool = await get_variable_pool()
        
        # 删除变量
        success = await pool.delete_variable(
            name=name,
            scope=scope,
            user_sub=None,  # 不再支持用户级变量
            flow_id=flow_id,
            conversation_id=None,  # 不再使用conversation_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="变量不存在"
            )
        
        return ResponseData(
            code=200,
            message="变量删除成功",
            result={"variable_name": name}
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除变量失败: {str(e)}"
        )


@router.get(
    "/get",
    responses={
        status.HTTP_200_OK: {"model": VariableResponse},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def get_variable(
    user_sub: Annotated[str, Depends(get_user)],
    name: str = Query(..., description="变量名称"),
    scope: VariableScope = Query(..., description="变量作用域"),
    flow_id: Optional[str] = Query(default=None, description="流程ID（环境级和对话级变量必需）"),
) -> VariableResponse:
    """获取单个变量"""
    try:
        pool = await get_variable_pool()
        
        # 获取变量
        variable = await pool.get_variable(
            name=name,
            scope=scope,
            user_sub=None,  # 不再支持用户级变量
            flow_id=flow_id if scope in [VariableScope.ENVIRONMENT, VariableScope.CONVERSATION] else None,
            conversation_id=None,  # 不再使用conversation_id
        )
        
        if not variable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="变量不存在"
            )
        
        # 检查权限
        if not variable.can_access(user_sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问此变量"
            )
        
        # 构建响应
        var_dict = variable.to_dict()
        return VariableResponse(
            name=variable.name,
            var_type=variable.var_type.value,
            scope=variable.scope.value,
            value=str(var_dict["value"]) if var_dict["value"] is not None else "",
            description=variable.metadata.description,
            created_at=variable.metadata.created_at.isoformat(),
            updated_at=variable.metadata.updated_at.isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取变量失败: {str(e)}"
        )


@router.get(
    "/list",
    responses={
        status.HTTP_200_OK: {"model": VariableListResponse},
    },
)
async def list_variables(
    user_sub: Annotated[str, Depends(get_user)],
    scope: VariableScope = Query(..., description="变量作用域"),
    flow_id: Optional[str] = Query(default=None, description="流程ID（环境级和对话级变量必需）"),
) -> VariableListResponse:
    """列出指定作用域的变量"""
    try:
        pool = await get_variable_pool()
        
        # 获取变量列表
        variables = await pool.list_variables(
            scope=scope,
            user_sub=None,  # 不再支持用户级变量
            flow_id=flow_id if scope in [VariableScope.ENVIRONMENT, VariableScope.CONVERSATION] else None,
            conversation_id=None,  # 不再使用conversation_id
        )
        
        # 过滤权限并构建响应
        filtered_variables = []
        for variable in variables:
            if variable.can_access(user_sub):
                var_dict = variable.to_dict()
                filtered_variables.append(VariableResponse(
                    name=variable.name,
                    var_type=variable.var_type.value,
                    scope=variable.scope.value,
                    value=str(var_dict["value"]) if var_dict["value"] is not None else "",
                    description=variable.metadata.description,
                    created_at=variable.metadata.created_at.isoformat(),
                    updated_at=variable.metadata.updated_at.isoformat(),
                ))
        
        return VariableListResponse(
            variables=filtered_variables,
            total=len(filtered_variables)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取变量列表失败: {str(e)}"
        )


@router.post(
    "/parse",
    responses={
        status.HTTP_200_OK: {"model": ParseTemplateResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
    },
)
async def parse_template(
    user_sub: Annotated[str, Depends(get_user)],
    request: ParseTemplateRequest = Body(...),
) -> ParseTemplateResponse:
    """解析模板中的变量引用"""
    try:
        # 创建变量解析器
        parser = VariableParser(
            user_sub=user_sub,
            flow_id=request.flow_id,
            conversation_id=None,  # 不再使用conversation_id
        )
        
        # 解析模板
        parsed_template = await parser.parse_template(request.template)
        
        # 提取使用的变量
        variables_used = await parser.extract_variables(request.template)
        
        return ParseTemplateResponse(
            parsed_template=parsed_template,
            variables_used=variables_used
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"解析模板失败: {str(e)}"
        )


@router.post(
    "/validate",
    responses={
        status.HTTP_200_OK: {"model": ValidateTemplateResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
    },
)
async def validate_template(
    user_sub: Annotated[str, Depends(get_user)],
    request: ParseTemplateRequest = Body(...),
) -> ValidateTemplateResponse:
    """验证模板中的变量引用是否有效"""
    try:
        # 创建变量解析器
        parser = VariableParser(
            user_sub=user_sub,
            flow_id=request.flow_id,
            conversation_id=None,  # 不再使用conversation_id
        )
        
        # 验证模板
        is_valid, invalid_refs = await parser.validate_template(request.template)
        
        return ValidateTemplateResponse(
            is_valid=is_valid,
            invalid_references=invalid_refs
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"验证模板失败: {str(e)}"
        )


@router.get(
    "/types",
    responses={
        status.HTTP_200_OK: {"model": ResponseData},
    },
)
async def get_variable_types() -> ResponseData:
    """获取支持的变量类型列表"""
    return ResponseData(
        code=200,
        message="获取变量类型成功",
        result={
            "types": [vtype.value for vtype in VariableType],
            "scopes": [scope.value for scope in VariableScope],
        }
    )


@router.post(
    "/clear-conversation",
    responses={
        status.HTTP_200_OK: {"model": ResponseData},
    },
)
async def clear_conversation_variables(
    user_sub: Annotated[str, Depends(get_user)],
    flow_id: str = Query(..., description="流程ID"),
) -> ResponseData:
    """清空指定工作流的对话级变量"""
    try:
        pool = await get_variable_pool()
        # 清空工作流的对话级变量
        await pool.clear_conversation_variables(flow_id)
        
        return ResponseData(
            code=200,
            message="工作流对话变量已清空",
            result={"flow_id": flow_id}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空对话变量失败: {str(e)}"
        ) 