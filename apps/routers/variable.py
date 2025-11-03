# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 变量管理 API"""

import json
import logging
from typing import Annotated, List, Optional, Dict, Any
from datetime import datetime, UTC

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.dependency import get_user
from apps.dependency.user import verify_user
from apps.scheduler.variable.pool_manager import get_pool_manager
from apps.scheduler.variable.type import VariableType, VariableScope
from apps.scheduler.variable.parser import VariableParser
from apps.schemas.response_data import ResponseData
from apps.services.flow import FlowManager

import re

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/variable",
    tags=["variable"],
    dependencies=[
        Depends(verify_user),
    ],
)


async def _get_predecessor_node_variables(
    user_sub: str,
    flow_id: str,
    conversation_id: Optional[str],
    current_step_id: str
) -> List:
    """获取前置节点的输出变量（优化版本，使用缓存）
    
    Args:
        user_sub: 用户ID
        flow_id: 流程ID
        conversation_id: 对话ID（可选，配置阶段可能为None）
        current_step_id: 当前步骤ID
        
    Returns:
        List: 前置节点的输出变量列表
    """
    try:
        variables = []
        pool_manager = await get_pool_manager()
        
        if conversation_id:
            # 运行阶段：从对话池获取实际的前置节点变量
            conversation_pool = await pool_manager.get_conversation_pool(conversation_id)
            if conversation_pool:
                # 获取所有对话变量
                all_conversation_vars = await conversation_pool.list_variables()
                
                # 筛选出前置节点的输出变量（格式为 node_id.key）
                for var in all_conversation_vars:
                    var_name = var.name
                    # 检查是否为节点输出变量格式（包含.且不是系统变量）
                    if "." in var_name and not var_name.startswith("system."):
                        # 提取节点ID
                        node_id = var_name.split(".")[0]
                        
                        # 检查是否为前置节点（这里可以根据需要添加更精确的前置判断逻辑）
                        if node_id != current_step_id:  # 不是当前节点的变量
                            variables.append(var)
        else:
            try:
                # 使用缓存获取变量列表
                from apps.services.predecessor_cache_service import PredecessorCacheService
                
                cached_var_data = await PredecessorCacheService.get_predecessor_variables_optimized(
                    flow_id, current_step_id, user_sub, max_wait_time=5
                )
                
                # 将缓存的变量数据转换为Variable对象
                for var_data in cached_var_data:
                    try:
                        var_name = var_data['name']
                        
                        # 检查是否为当前步骤的输出变量
                        if "." in var_name and not var_name.startswith("system."):
                            # 提取节点ID
                            node_id = var_name.split(".")[0]
                            
                            # 排除当前步骤的输出变量
                            if node_id == current_step_id:
                                continue  # 跳过当前步骤的输出变量
                        
                        from apps.scheduler.variable.variables import create_variable
                        from apps.scheduler.variable.base import VariableMetadata
                        from apps.scheduler.variable.type import VariableType, VariableScope
                        from datetime import datetime
                        
                        # 创建变量元数据
                        metadata = VariableMetadata(
                            name=var_name,
                            var_type=VariableType(var_data['var_type']),
                            scope=VariableScope(var_data['scope']),
                            description=var_data.get('description', ''),
                            created_by=user_sub,
                            created_at=datetime.fromisoformat(var_data['created_at'].replace('Z', '+00:00')),
                            updated_at=datetime.fromisoformat(var_data['updated_at'].replace('Z', '+00:00'))
                        )
                        
                        # 创建变量对象，并附加缓存的节点信息（使用None避免类型验证失败）
                        variable = create_variable(metadata, var_data.get('value'))
                        
                        # 将节点信息附加到变量对象上（用于后续响应格式化）
                        if hasattr(variable, '_cache_data'):
                            variable._cache_data = var_data
                        else:
                            # 如果对象不支持动态属性，我们可以创建一个包装类或者在响应时处理
                            setattr(variable, '_cache_data', var_data)
                            
                        variables.append(variable)
                        
                    except Exception as var_create_error:
                        logger.warning(f"创建缓存变量对象失败: {var_create_error}")
                        continue
                
                logger.info(f"配置阶段：为节点 {current_step_id} 找到前置节点变量总数: {len([v for v in variables if hasattr(v, 'name') and '.' in v.name and not v.name.startswith('system.')])}")
                            
            except Exception as flow_error:
                logger.warning(f"配置阶段获取前置节点变量失败，降级到实时解析: {flow_error}")
                # 降级到原有的实时解析逻辑
                predecessor_vars = await _get_predecessor_variables_from_topology(
                    flow_id, current_step_id, user_sub
                )
                variables.extend(predecessor_vars)
        
        return variables
        
    except Exception as e:
        logger.error(f"获取前置节点变量失败: {e}")
        return []





# 请求和响应模型
class CreateVariableRequest(BaseModel):
    """创建变量请求"""
    name: str = Field(description="变量名称")
    var_type: VariableType = Field(description="变量类型")
    scope: VariableScope = Field(description="变量作用域")
    value: Optional[Any] = Field(default=None, description="变量值")
    description: Optional[str] = Field(default=None, description="变量描述")
    flow_id: Optional[str] = Field(default=None, description="流程ID（环境级和对话级变量必需）")
    # 文件类型变量专用字段
    supported_types: Optional[List[str]] = Field(default=None, description="支持的文件类型（文件类型变量专用）")
    upload_methods: Optional[List[str]] = Field(default=None, description="支持的上传方式列表（文件类型变量专用）")
    max_files: Optional[int] = Field(default=None, description="最大上传文件数（文件类型变量专用）")
    max_file_size: Optional[int] = Field(default=None, description="单个文件最大大小（MB，文件类型变量专用）")
    required: Optional[bool] = Field(default=None, description="文件是否必填（文件类型变量专用）")


class UpdateVariableRequest(BaseModel):
    """更新变量请求"""
    value: Optional[Any] = Field(default=None, description="新的变量值")
    var_type: Optional[VariableType] = Field(default=None, description="新的变量类型")
    description: Optional[str] = Field(default=None, description="新的变量描述")
    # 文件类型变量专用字段（用于更新文件配置）
    supported_types: Optional[List[str]] = Field(default=None, description="支持的文件类型（文件类型变量专用）")
    upload_methods: Optional[List[str]] = Field(default=None, description="支持的上传方式列表（文件类型变量专用）")
    max_files: Optional[int] = Field(default=None, description="最大上传文件数（文件类型变量专用）")
    max_file_size: Optional[int] = Field(default=None, description="单个文件最大大小（MB，文件类型变量专用）")
    required: Optional[bool] = Field(default=None, description="文件是否必填（文件类型变量专用）")


class VariableResponse(BaseModel):
    """变量响应"""
    name: str = Field(description="变量名称")
    var_type: str = Field(description="变量类型")
    scope: str = Field(description="变量作用域")
    value: str = Field(description="变量值")
    description: Optional[str] = Field(description="变量描述")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    step: Optional[str] = Field(default=None, description="节点名称（前置节点变量专用）")
    step_id: Optional[str] = Field(default=None, description="节点ID（前置节点变量专用）")


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
        
        # 类型转换和验证
        converted_value = None
        if request.value is not None:
            try:
                # 对于文件类型，使用异步转换
                if request.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                    # 构建文件类型变量的完整信息
                    file_config = {
                        "supported_types": request.supported_types or [],
                        "upload_methods": request.upload_methods or ["manual"],
                        "max_files": request.max_files or (1 if request.var_type == VariableType.FILE else 10),
                        "max_file_size": request.max_file_size or (10 * 1024 * 1024), # 默认10MB
                        "required": request.required if request.required is not None else False # 默认非必填
                    }
                    
                    # 如果提供了value，合并到配置中
                    if isinstance(request.value, dict):
                        file_config.update(request.value)
                    else:
                        # 如果value不是字典，将其作为文件ID处理
                        if request.var_type == VariableType.FILE:
                            file_config["file_id"] = request.value if isinstance(request.value, str) else ""
                        else:
                            file_config["file_ids"] = request.value if isinstance(request.value, list) else []
                    
                    converted_value = await convert_file_value_by_type(
                        file_config, 
                        request.var_type, 
                        user_sub, 
                        conversation_id=None,  # 创建变量时没有conversation_id
                        flow_id=request.flow_id
                    )
                else:
                    converted_value = convert_value_by_type(request.value, request.var_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"变量值类型转换失败: {str(e)}"
                )
        elif request.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
            # 文件类型变量但没有提供value，创建默认结构
            converted_value = await convert_file_value_by_type(
                {
                    "supported_types": request.supported_types or [],
                    "upload_methods": request.upload_methods or ["manual"],
                    "max_files": request.max_files or (1 if request.var_type == VariableType.FILE else 10),
                    "max_file_size": request.max_file_size or (10 * 1024 * 1024), # 默认10MB
                    "required": request.required if request.required is not None else False # 默认非必填
                }, 
                request.var_type, 
                user_sub, 
                conversation_id=getattr(request, 'conversation_id', None),
                flow_id=request.flow_id
            )
        
        pool_manager = await get_pool_manager()
        
        # 根据作用域获取合适的变量池
        if request.scope == VariableScope.USER:
            # 用户级变量需要user_sub参数
            if not user_sub:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户级变量需要用户身份"
                )
            pool = await pool_manager.get_user_pool(user_sub)
        elif request.scope == VariableScope.ENVIRONMENT:
            # 环境级变量需要flow_id参数
            if not request.flow_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="环境级变量需要flow_id参数"
                )
            pool = await pool_manager.get_flow_pool(request.flow_id)
        elif request.scope == VariableScope.CONVERSATION:
            # 对话级变量需要flow_id参数，用于创建模板
            if not request.flow_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="对话级变量需要flow_id参数"
                )
            # 对话级变量模板在流程池中定义
            pool = await pool_manager.get_flow_pool(request.flow_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的变量作用域: {request.scope.value}"
            )
        
        if not pool:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法获取变量池"
            )
        
        # 根据作用域创建不同类型的变量
        if request.scope == VariableScope.CONVERSATION:
            # 创建对话变量模板
            variable = await pool.add_conversation_template(
                name=request.name,
                var_type=request.var_type,
                default_value=converted_value,
                description=request.description,
                created_by=user_sub
            )
        else:
            # 创建其他类型的变量
            variable = await pool.add_variable(
                name=request.name,
                var_type=request.var_type,
                value=converted_value,
                description=request.description,
                created_by=user_sub
            )

        
        return ResponseData(
            code=200,
            message="变量创建成功",
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
    conversation_id: Optional[str] = Query(default=None, description="对话ID（对话级变量运行时必需）"),
    request: UpdateVariableRequest = Body(...),
) -> ResponseData:
    """更新变量值"""
    try:
        pool_manager = await get_pool_manager()
        
        # 根据作用域获取合适的变量池
        if scope == VariableScope.USER:
            if not user_sub:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户级变量需要用户身份"
                )
            pool = await pool_manager.get_user_pool(user_sub)
        elif scope == VariableScope.ENVIRONMENT:
            if not flow_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="环境级变量需要flow_id参数"
                )
            pool = await pool_manager.get_flow_pool(flow_id)
        elif scope == VariableScope.CONVERSATION:
            if conversation_id:
                # 运行时：使用对话池，如果不存在则创建
                if not flow_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="对话级变量运行时需要conversation_id和flow_id参数"
                    )
                pool = await pool_manager.get_conversation_pool(conversation_id)
                if not pool:
                    # 对话池不存在，自动创建
                    pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
            elif flow_id:
                # 配置时：使用流程池
                pool = await pool_manager.get_flow_pool(flow_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="对话级变量需要conversation_id（运行时）或flow_id（配置时）参数"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的变量作用域: {scope.value}"
            )
        
        if not pool:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法获取变量池"
            )
        
        # 类型转换和验证（仅当提供了新值和新类型时）
        converted_value = request.value
        if request.value is not None and request.var_type is not None:
            try:
                # 对于文件类型，使用异步转换
                if request.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                    # 如果提供了文件专用字段，构建完整的文件配置
                    file_value = request.value
                    if any([request.supported_types, request.upload_methods, request.max_files, request.max_file_size]):
                        # 构建文件类型变量的完整信息
                        file_config = {
                            "supported_types": request.supported_types or [],
                            "upload_methods": request.upload_methods or ["manual"],
                            "max_files": request.max_files or (1 if request.var_type == VariableType.FILE else 10),
                            "max_file_size": request.max_file_size or (10 * 1024 * 1024), # 默认10MB
                            "required": request.required if request.required is not None else False # 默认非必填
                        }
                        
                        # 如果提供了value，合并到配置中
                        if isinstance(request.value, dict):
                            file_config.update(request.value)
                        else:
                            # 如果value不是字典，将其作为文件ID处理
                            if request.var_type == VariableType.FILE:
                                file_config["file_id"] = request.value if isinstance(request.value, str) else ""
                            else:
                                file_config["file_ids"] = request.value if isinstance(request.value, list) else []
                        
                        file_value = file_config
                    
                    converted_value = await convert_file_value_by_type(
                        file_value, 
                        request.var_type, 
                        user_sub, 
                        conversation_id=conversation_id,
                        flow_id=flow_id
                    )
                else:
                    converted_value = convert_value_by_type(request.value, request.var_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"变量值类型转换失败: {str(e)}"
                )
        elif request.value is not None or any([request.supported_types, request.upload_methods, request.max_files, request.max_file_size]):
            # 如果只提供了值或文件配置但没有类型，需要获取现有变量的类型
            try:
                existing_variable = await pool.get_variable(name)
                # 对于文件类型，使用异步转换
                if existing_variable.metadata.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                    # 如果提供了文件专用字段，需要构建文件配置
                    file_value = request.value
                    if any([request.supported_types, request.upload_methods, request.max_files, request.max_file_size]):
                        # 获取现有的文件配置
                        existing_config = {}
                        if isinstance(existing_variable.value, dict):
                            existing_config = existing_variable.value.copy()
                        
                        # 构建新的文件配置
                        file_config = {
                            "supported_types": request.supported_types or existing_config.get("supported_types", []),
                            "upload_methods": request.upload_methods or existing_config.get("upload_methods", ["manual"]),
                            "max_files": request.max_files or existing_config.get("max_files", (1 if existing_variable.metadata.var_type == VariableType.FILE else 10)),
                            "max_file_size": request.max_file_size or existing_config.get("max_file_size", (10 * 1024 * 1024)),
                            "required": request.required if request.required is not None else existing_config.get("required", False)
                        }
                        
                        # 保留现有的文件ID
                        if existing_variable.metadata.var_type == VariableType.FILE:
                            file_config["file_id"] = existing_config.get("file_id", "")
                        else:
                            file_config["file_ids"] = existing_config.get("file_ids", [])
                        
                        # 如果提供了新的value，使用新的value处理文件ID
                        if request.value is not None:
                            if isinstance(request.value, dict):
                                file_config.update(request.value)
                            else:
                                # 如果value不是字典，将其作为文件ID处理
                                if existing_variable.metadata.var_type == VariableType.FILE:
                                    file_config["file_id"] = request.value if isinstance(request.value, str) else ""
                                else:
                                    file_config["file_ids"] = request.value if isinstance(request.value, list) else []
                        
                        file_value = file_config
                    
                    converted_value = await convert_file_value_by_type(
                        file_value, 
                        existing_variable.metadata.var_type, 
                        user_sub, 
                        conversation_id=conversation_id,
                        flow_id=flow_id
                    )
                else:
                    converted_value = convert_value_by_type(request.value, existing_variable.metadata.var_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"变量值类型转换失败: {str(e)}"
                )
            except Exception:
                # 如果获取现有变量失败，使用原值
                converted_value = request.value
        
        # 更新变量
        variable = await pool.update_variable(
            name=name,
            value=converted_value,
            var_type=request.var_type,
            description=request.description
        )
        
        return ResponseData(
            code=200,
            message="变量更新成功",
            result={"variable_name": variable.name}
        )
        
    except ValueError as e:
        logger.error(f"更新变量失败(ValueError): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        logger.error(f"更新变量失败(PermissionError): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"更新变量失败(Exception): {e}", exc_info=True)
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
    conversation_id: Optional[str] = Query(default=None, description="对话ID（对话级变量运行时必需）"),
) -> ResponseData:
    """删除变量"""
    try:
        pool_manager = await get_pool_manager()
        
        # 根据作用域获取合适的变量池
        if scope == VariableScope.USER:
            if not user_sub:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="用户级变量需要用户身份"
                )
            pool = await pool_manager.get_user_pool(user_sub)
        elif scope == VariableScope.ENVIRONMENT:
            if not flow_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="环境级变量需要flow_id参数"
                )
            pool = await pool_manager.get_flow_pool(flow_id)
        elif scope == VariableScope.CONVERSATION:
            if conversation_id:
                # 运行时：使用对话池，如果不存在则创建
                if not flow_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="对话级变量运行时需要conversation_id和flow_id参数"
                    )
                pool = await pool_manager.get_conversation_pool(conversation_id)
                if not pool:
                    # 对话池不存在，自动创建
                    pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
            elif flow_id:
                # 配置时：使用流程池
                pool = await pool_manager.get_flow_pool(flow_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="对话级变量需要conversation_id（运行时）或flow_id（配置时）参数"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的变量作用域: {scope.value}"
            )
        
        if not pool:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法获取变量池"
            )
        
        # 删除变量
        success = await pool.delete_variable(name)
        
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
    conversation_id: Optional[str] = Query(default=None, description="对话ID（系统级和对话级变量必需）"),
) -> VariableResponse:
    """获取单个变量"""
    try:
        pool_manager = await get_pool_manager()
        
        # 根据作用域获取变量
        variable = await pool_manager.get_variable_from_any_pool(
            name=name,
            scope=scope,
            user_id=user_sub if scope == VariableScope.USER else None,
            flow_id=flow_id if scope in [VariableScope.SYSTEM, VariableScope.ENVIRONMENT, VariableScope.CONVERSATION] else None,
            conversation_id=conversation_id if scope in [VariableScope.SYSTEM, VariableScope.CONVERSATION] else None
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
    conversation_id: Optional[str] = Query(default=None, description="对话ID（系统级和对话级变量必需）"),
    current_step_id: Optional[str] = Query(default=None, description="当前步骤ID（用于获取前置节点变量）"),
    exclude_pattern: Optional[str] = Query(default=None, description="排除模式：'step_id'排除包含.的变量名")
) -> VariableListResponse:
    """列出指定作用域的变量"""
    try:
        pool_manager = await get_pool_manager()
        
        # 获取变量列表
        variables = await pool_manager.list_variables_from_any_pool(
            scope=scope,
            user_id=user_sub if scope == VariableScope.USER else None,
            flow_id=flow_id if scope in [VariableScope.SYSTEM, VariableScope.ENVIRONMENT, VariableScope.CONVERSATION] else None,
            conversation_id=conversation_id if scope in [VariableScope.SYSTEM, VariableScope.CONVERSATION] else None
        )
        
        # 如果是对话级变量且提供了current_step_id，则额外获取前置节点的输出变量
        if scope == VariableScope.CONVERSATION and current_step_id and flow_id:
            predecessor_variables = await _get_predecessor_node_variables(
                user_sub, flow_id, conversation_id, current_step_id
            )
            variables.extend(predecessor_variables)
        
        # 应用排除模式过滤
        if exclude_pattern == "step_id" and scope == VariableScope.CONVERSATION:
            # 排除包含"."的变量名（即节点特定变量），只保留全局对话变量
            variables = [var for var in variables if "." not in var.name]
        
        # 过滤权限并构建响应
        filtered_variables = []
        for variable in variables:
            if variable.can_access(user_sub):
                var_dict = variable.to_dict()
                
                # 检查是否为前置节点变量
                is_predecessor_var = (
                    "." in variable.name and 
                    not variable.name.startswith("system.") and
                    scope == VariableScope.CONVERSATION and
                    flow_id
                )
                
                if is_predecessor_var:
                    # 前置节点变量特殊处理
                    parts = variable.name.split(".", 1)
                    if len(parts) == 2:
                        step_id, var_name = parts
                        
                        # 确保不是当前步骤的输出变量（双重保险）
                        if current_step_id and step_id == current_step_id:
                            continue
                        
                        # 优先使用缓存数据中的节点信息
                        if hasattr(variable, '_cache_data') and variable._cache_data:
                            cache_data = variable._cache_data
                            step_name = cache_data.get('step_name', step_id)
                            step_id_from_cache = cache_data.get('step_id', step_id)
                        else:
                            # 降级到实时获取节点信息
                            node_info = await _get_node_info_by_step_id(flow_id, step_id)
                            step_name = node_info["name"]
                            step_id_from_cache = node_info["step_id"]
                        
                        filtered_variables.append(VariableResponse(
                            name=var_name,  # 只保留变量名部分
                            var_type=variable.var_type.value,
                            scope=variable.scope.value,
                            value=str(var_dict["value"]) if var_dict["value"] is not None else "",
                            description=variable.metadata.description,
                            created_at=variable.metadata.created_at.isoformat(),
                            updated_at=variable.metadata.updated_at.isoformat(),
                            step=step_name,  # 节点名称
                            step_id=step_id_from_cache  # 节点ID
                        ))
                    else:
                        # 降级处理，如果格式不符合预期
                        filtered_variables.append(VariableResponse(
                            name=variable.name,
                            var_type=variable.var_type.value,
                            scope=variable.scope.value,
                            value=str(var_dict["value"]) if var_dict["value"] is not None else "",
                            description=variable.metadata.description,
                            created_at=variable.metadata.created_at.isoformat(),
                            updated_at=variable.metadata.updated_at.isoformat(),
                        ))
                else:
                    # 普通变量
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
            user_id=user_sub,
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
            user_id=user_sub,
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
        pool_manager = await get_pool_manager()
        # 清空工作流的对话级变量
        await pool_manager.clear_conversation_variables(flow_id)
        
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


async def _get_node_info_by_step_id(flow_id: str, step_id: str) -> Dict[str, str]:
    """根据step_id获取节点信息"""
    try:
        flow_item = await _get_flow_by_flow_id(flow_id)
        if not flow_item:
            return {"name": step_id, "step_id": step_id}  # 降级返回step_id作为名称
        
        # 查找对应的节点
        for node in flow_item.nodes:
            if node.step_id == step_id:
                return {
                    "name": node.name or step_id,  # 如果没有名称则使用step_id
                    "step_id": step_id
                }
                
        # 如果没有找到节点，返回默认值
        return {"name": step_id, "step_id": step_id}
        
    except Exception as e:
        logger.error(f"获取节点信息失败: {e}")
        return {"name": step_id, "step_id": step_id}


async def _get_predecessor_variables_from_topology(
    flow_id: str, 
    current_step_id: str, 
    user_sub: str
) -> List:
    """通过工作流拓扑分析获取前置节点变量"""
    try:
        variables = []
        
        # 直接通过flow_id获取工作流拓扑信息
        flow_item = await _get_flow_by_flow_id(flow_id)
        if not flow_item:
            logger.warning(f"无法获取工作流信息: flow_id={flow_id}")
            return variables
        
        # 分析前置节点
        predecessor_nodes = _find_predecessor_nodes(flow_item, current_step_id)
        
        # 为每个前置节点创建潜在的输出变量
        for node in predecessor_nodes:
            node_vars = await _create_node_output_variables(node, user_sub)
            variables.extend(node_vars)
        
        logger.info(f"通过拓扑分析为节点 {current_step_id} 创建了 {len(variables)} 个前置节点变量")
        return variables
        
    except Exception as e:
        logger.error(f"通过拓扑分析获取前置节点变量失败: {e}")
        return []


async def _get_flow_by_flow_id(flow_id: str):
    """直接通过flow_id获取工作流信息"""
    try:
        from apps.common.mongo import MongoDB
        
        app_collection = MongoDB().get_collection("app")
        
        # 查询包含此flow_id的app，同时获取app_id
        app_record = await app_collection.find_one(
            {"flows.id": flow_id},
            {"_id": 1}
        )
        
        if not app_record:
            logger.warning(f"未找到包含flow_id {flow_id} 的应用")
            return None
            
        app_id = app_record["_id"]
        
        # 使用现有的FlowManager方法获取flow
        flow_item = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
        return flow_item
        
    except Exception as e:
        logger.error(f"通过flow_id获取工作流失败: {e}")
        return None


def _find_predecessor_nodes(flow_item, current_step_id: str) -> List:
    """在工作流中查找前置节点"""
    try:
        predecessor_nodes = []
        
        # 遍历边，找到指向当前节点的边
        for edge in flow_item.edges:
            if edge.target_node == current_step_id:
                # 找到前置节点
                source_node = next(
                    (node for node in flow_item.nodes if node.step_id == edge.source_node),
                    None
                )
                if source_node:
                    predecessor_nodes.append(source_node)
        
        logger.info(f"为节点 {current_step_id} 找到 {len(predecessor_nodes)} 个前置节点")
        return predecessor_nodes
        
    except Exception as e:
        logger.error(f"查找前置节点失败: {e}")
        return []


async def _create_node_output_variables(node, user_sub: str) -> List:
    """根据节点的output_parameters配置创建输出变量"""
    try:
        from apps.scheduler.variable.variables import create_variable
        from apps.scheduler.variable.base import VariableMetadata
        from datetime import datetime, UTC
        
        variables = []
        node_id = node.step_id
        
        # 调试：输出节点的完整参数信息
        logger.info(f"节点 {node_id} 的参数结构: {node.parameters}")
        
        # 统一从节点的output_parameters创建变量
        output_params = {}
        if hasattr(node, 'parameters') and node.parameters:
            # 尝试不同的访问方式
            if isinstance(node.parameters, dict):
                output_params = node.parameters.get('output_parameters', {})
                logger.info(f"从字典中获取output_parameters: {output_params}")
            else:
                output_params = getattr(node.parameters, 'output_parameters', {})
                logger.info(f"从对象属性中获取output_parameters: {output_params}")
        
        # 如果没有配置output_parameters，跳过此节点
        if not output_params:
            logger.info(f"节点 {node_id} 没有配置output_parameters，跳过创建输出变量")
            return variables
        
        # 遍历output_parameters中的每个key-value对，创建对应的变量
        for param_name, param_config in output_params.items():
            # 解析参数配置
            if isinstance(param_config, dict):
                param_type = param_config.get('type', 'string')
                description = param_config.get('description', '')
            else:
                # 如果param_config不是字典，可能是简单的类型字符串
                param_type = str(param_config) if param_config else 'string'
                description = ''
            
            # 确定变量类型
            var_type = VariableType.STRING  # 默认类型
            if param_type == 'number':
                var_type = VariableType.NUMBER
            elif param_type == 'boolean':
                var_type = VariableType.BOOLEAN
            elif param_type == 'object':
                var_type = VariableType.OBJECT
            elif param_type == 'array' or param_type == 'array[any]':
                var_type = VariableType.ARRAY_ANY
            elif param_type == 'array[string]':
                var_type = VariableType.ARRAY_STRING
            elif param_type == 'array[number]':
                var_type = VariableType.ARRAY_NUMBER
            elif param_type == 'array[object]':
                var_type = VariableType.ARRAY_OBJECT
            elif param_type == 'array[boolean]':
                var_type = VariableType.ARRAY_BOOLEAN
            elif param_type == 'array[file]':
                var_type = VariableType.ARRAY_FILE
            elif param_type == 'array[secret]':
                var_type = VariableType.ARRAY_SECRET
            elif param_type == 'file':
                var_type = VariableType.FILE
            elif param_type == 'secret':
                var_type = VariableType.SECRET
            
            # 创建变量元数据
            metadata = VariableMetadata(
                name=f"{node_id}.{param_name}",
                var_type=var_type,
                scope=VariableScope.CONVERSATION,
                description=description or f"来自节点 {node_id} 的输出参数 {param_name}",
                created_by=user_sub,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            
            # 创建变量对象（使用None作为默认值，避免类型验证失败）
            variable = create_variable(metadata, None)  # 配置阶段的潜在变量，值为None
            variables.append(variable)
        
        logger.info(f"为节点 {node_id} 创建了 {len(variables)} 个输出变量: {[v.name for v in variables]}")
        return variables
        
    except Exception as e:
        logger.error(f"创建节点输出变量失败: {e}")
        return []


def convert_string_value_by_type(value: str, var_type: VariableType) -> Any:
    """
    根据变量类型将字符串值转换为对应的Python类型
    
    Args:
        value: 字符串格式的值
        var_type: 变量类型
        
    Returns:
        转换后的值
        
    Raises:
        ValueError: 当值无法转换为指定类型时
    """
    if value is None:
        return None
        
    try:
        match var_type:
            case VariableType.STRING | VariableType.SECRET:
                return str(value)
                
            case VariableType.NUMBER:
                # 尝试转换为数字
                if isinstance(value, str) and value.strip() == "":
                    return 0
                # 如果包含小数点，转换为float，否则转换为int
                if '.' in str(value):
                    return float(value)
                else:
                    return int(value)
                    
            case VariableType.BOOLEAN:
                # 处理布尔值转换
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    lower_value = value.lower().strip()
                    if lower_value in ('true', '1', 'yes', 'on'):
                        return True
                    elif lower_value in ('false', '0', 'no', 'off'):
                        return False
                    else:
                        raise ValueError(f"无法将 '{value}' 转换为布尔值")
                return bool(value)
                
            case VariableType.OBJECT:
                # 处理对象类型
                if isinstance(value, dict):
                    return value
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析JSON对象: {e}")
                return dict(value)
                
            case VariableType.ARRAY_STRING:
                # 处理字符串数组
                if isinstance(value, list):
                    return [str(item) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return [str(item) for item in parsed]
                        else:
                            # 尝试按逗号分割
                            return [item.strip() for item in value.split(',') if item.strip()]
                    except json.JSONDecodeError:
                        # 按逗号分割
                        return [item.strip() for item in value.split(',') if item.strip()]
                return list(value)
                
            case VariableType.ARRAY_NUMBER:
                # 处理数字数组
                if isinstance(value, list):
                    return [float(item) if '.' in str(item) else int(item) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            result = []
                            for item in parsed:
                                if isinstance(item, (int, float)):
                                    result.append(item)
                                else:
                                    result.append(float(item) if '.' in str(item) else int(item))
                            return result
                        else:
                            raise ValueError("期望数组格式")
                    except (json.JSONDecodeError, ValueError) as e:
                        raise ValueError(f"无法解析数字数组: {e}")
                return list(value)
                
            case VariableType.ARRAY_BOOLEAN:
                # 处理布尔数组
                if isinstance(value, list):
                    return [convert_string_value_by_type(str(item), VariableType.BOOLEAN) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return [convert_string_value_by_type(str(item), VariableType.BOOLEAN) for item in parsed]
                        else:
                            raise ValueError("期望数组格式")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析布尔数组: {e}")
                return list(value)
                
            case VariableType.ARRAY_OBJECT:
                # 处理对象数组
                if isinstance(value, list):
                    return [convert_string_value_by_type(json.dumps(item) if not isinstance(item, str) else item, VariableType.OBJECT) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return parsed  # 已经是解析后的对象数组
                        else:
                            raise ValueError("期望数组格式")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析对象数组: {e}")
                return list(value)
                
            case VariableType.FILE | VariableType.ARRAY_FILE:
                # 文件类型需要保持字典格式或正确解析字符串
                if isinstance(value, dict):
                    return value
                elif isinstance(value, str):
                    try:
                        # 先尝试JSON解析
                        return json.loads(value)
                    except json.JSONDecodeError:
                        try:
                            # 如果JSON解析失败，尝试Python字典格式（单引号）
                            import ast
                            return ast.literal_eval(value)
                        except (ValueError, SyntaxError):
                            # 如果都失败，返回字符串（向后兼容）
                            return str(value)
                else:
                    # 其他类型尝试转换为字符串
                    return str(value)
                
            case VariableType.ARRAY_SECRET:
                # 密钥数组
                if isinstance(value, list):
                    return [str(item) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return [str(item) for item in parsed]
                        else:
                            raise ValueError("期望数组格式")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析密钥数组: {e}")
                return list(value)
                
            case _:
                # 默认返回字符串
                return str(value)
                
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"无法将值 '{value}' 转换为类型 '{var_type.value}': {str(e)}")


def convert_value_by_type(value: Any, var_type: VariableType) -> Any:
    """根据变量类型转换值"""
    try:
        match var_type:
            case VariableType.STRING:
                return str(value)
                
            case VariableType.NUMBER:
                if isinstance(value, (int, float)):
                    return value
                elif isinstance(value, str):
                    return float(value) if '.' in value else int(value)
                else:
                    return float(value)
                    
            case VariableType.BOOLEAN:
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    lower_val = value.lower()
                    if lower_val in ('true', '1', 'yes', 'on'):
                        return True
                    elif lower_val in ('false', '0', 'no', 'off'):
                        return False
                    else:
                        raise ValueError(f"无法将字符串 '{value}' 转换为布尔值")
                elif isinstance(value, (int, float)):
                    return bool(value)
                else:
                    return bool(value)
                    
            case VariableType.OBJECT:
                if isinstance(value, dict):
                    return value
                elif isinstance(value, str):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析JSON对象: {e}")
                else:
                    raise ValueError(f"无法将类型 {type(value).__name__} 转换为对象")
                    
            case VariableType.SECRET:
                return str(value)
                
            case VariableType.ARRAY_STRING:
                # 如果已经是列表，检查元素类型
                if isinstance(value, list):
                    return [str(item) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return [str(item) for item in parsed]
                        else:
                            # 尝试按逗号分割
                            return [item.strip() for item in value.split(',') if item.strip()]
                    except json.JSONDecodeError:
                        # 按逗号分割
                        return [item.strip() for item in value.split(',') if item.strip()]
                else:
                    return [str(value)]
                
            case VariableType.ARRAY_NUMBER:
                # 如果已经是列表，检查元素类型
                if isinstance(value, list):
                    result = []
                    for item in value:
                        if isinstance(item, (int, float)):
                            result.append(item)
                        else:
                            result.append(float(item) if '.' in str(item) else int(item))
                    return result
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            result = []
                            for item in parsed:
                                if isinstance(item, (int, float)):
                                    result.append(item)
                                else:
                                    result.append(float(item) if '.' in str(item) else int(item))
                            return result
                        else:
                            raise ValueError("期望数组格式")
                    except (json.JSONDecodeError, ValueError) as e:
                        raise ValueError(f"无法解析数字数组: {e}")
                else:
                    return [value]
                
            case VariableType.ARRAY_BOOLEAN:
                # 如果已经是列表，检查元素类型
                if isinstance(value, list):
                    return [convert_value_by_type(item, VariableType.BOOLEAN) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return [convert_value_by_type(item, VariableType.BOOLEAN) for item in parsed]
                        else:
                            raise ValueError("期望数组格式")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析布尔数组: {e}")
                else:
                    return [value]
                
            case VariableType.ARRAY_OBJECT:
                # 如果已经是列表，检查元素类型
                if isinstance(value, list):
                    return [convert_value_by_type(item, VariableType.OBJECT) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return parsed  # 已经是解析后的对象数组
                        else:
                            raise ValueError("期望数组格式")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析对象数组: {e}")
                else:
                    return [value]
                
            case VariableType.ARRAY_SECRET:
                # 密钥数组
                if isinstance(value, list):
                    return [str(item) for item in value]
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return [str(item) for item in parsed]
                        else:
                            raise ValueError("期望数组格式")
                    except json.JSONDecodeError as e:
                        raise ValueError(f"无法解析密钥数组: {e}")
                else:
                    return [str(value)]
                
            case _:
                # 默认返回字符串
                return str(value)
                
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"无法将值 '{value}' (类型: {type(value).__name__}) 转换为类型 '{var_type.value}': {str(e)}")


async def convert_file_value_by_type(value: Any, var_type: VariableType, user_sub: str, conversation_id: Optional[str] = None, flow_id: Optional[str] = None) -> Any:
    """异步处理文件类型的值转换"""
    if var_type not in [VariableType.FILE, VariableType.ARRAY_FILE]:
        return value
    
    # 文件类型变量的默认存储结构
    if var_type == VariableType.FILE:
        # 单个文件变量结构
        if isinstance(value, dict):
            # 如果已经是字典格式，验证并返回
            if "file_id" in value:
                return value
            else:
                # 缺少必要字段，使用默认结构
                return {
                    "file_id": "",  # 文件ID，默认为空
                    "supported_types": value.get("supported_types", []),  # 支持的文件类型
                    "upload_methods": value.get("upload_methods", ["manual"]),  # 支持的上传方式
                    "max_files": value.get("max_files", 1),  # 最大文件数（单个文件为1）
                    "max_file_size": value.get("max_file_size", 10 * 1024 * 1024), # 默认10MB
                    "required": value.get("required", False)  # 是否必填
                }
        elif isinstance(value, str):
            # 如果是字符串，可能是文件ID或文件路径
            if len(value) == 36 and value.count('-') == 4:
                # 是文件ID格式，转换为字典结构
                return {
                    "file_id": value,
                    "supported_types": [],
                    "upload_methods": ["manual"],
                    "max_files": 1,
                    "max_file_size": 10 * 1024 * 1024, # 默认10MB
                    "required": False  # 默认非必填
                }
            else:
                # 不是文件ID，使用默认结构
                        return {
            "file_id": "",
            "supported_types": [],
            "upload_methods": ["manual"],
            "max_files": 1,
            "max_file_size": 10 * 1024 * 1024, # 默认10MB
            "required": False  # 默认非必填
        }
        else:
            # 其他类型，使用默认结构
            return {
                "file_id": "",
                "supported_types": [],
                "upload_methods": ["manual"],
                "max_files": 1,
                "max_file_size": 10 * 1024 * 1024, # 默认10MB
                "required": False  # 默认非必填
            }
    
    elif var_type == VariableType.ARRAY_FILE:
        # 文件列表变量结构
        if isinstance(value, dict):
            # 如果已经是字典格式，验证并返回
            if "file_ids" in value:
                return value
            else:
                # 缺少必要字段，使用默认结构
                return {
                    "file_ids": [],  # 文件ID列表，默认为空
                    "supported_types": value.get("supported_types", []),  # 支持的文件类型
                    "upload_methods": value.get("upload_methods", ["manual"]),  # 支持的上传方式
                    "max_files": value.get("max_files", 10),  # 最大文件数
                    "max_file_size": value.get("max_file_size", 10 * 1024 * 1024), # 默认10MB
                    "required": value.get("required", False)  # 是否必填
                }
        elif isinstance(value, list):
            # 如果是列表，可能是文件ID列表
            if all(isinstance(item, str) and len(item) == 36 and item.count('-') == 4 for item in value):
                # 是文件ID列表格式，转换为字典结构
                return {
                    "file_ids": value,
                    "supported_types": [],
                    "upload_methods": ["manual"],
                    "max_files": len(value),
                    "max_file_size": 10 * 1024 * 1024, # 默认10MB
                    "required": False  # 默认非必填
                }
            else:
                # 不是文件ID列表，使用默认结构
                return {
                    "file_ids": [],
                    "supported_types": [],
                    "upload_methods": ["manual"],
                    "max_files": 10,
                    "max_file_size": 10 * 1024 * 1024, # 默认10MB
                    "required": False  # 默认非必填
                }
        else:
            # 其他类型，使用默认结构
            return {
                "file_ids": [],
                "supported_types": [],
                "upload_methods": ["manual"],
                "max_files": 10,
                "max_file_size": 10 * 1024 * 1024, # 默认10MB
                "required": False  # 默认非必填
            }
    
    return value