# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""步骤参数相关路由"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_personal_token
from apps.schemas.parameters import Type
from apps.schemas.response_data import GetOperaRsp, GetParamsRsp
from apps.services.appcenter import AppCenterManager
from apps.services.flow import FlowManager
from apps.services.parameter import ParameterManager

router = APIRouter(
    prefix="/api/parameter",
    tags=["parameter"],
    dependencies=[
        Depends(verify_personal_token),
    ],
)


@router.get("", response_model=GetParamsRsp)
async def get_parameters(
    request: Request, appId: uuid.UUID, flowId: str, stepId: uuid.UUID,  # noqa: N803
) -> JSONResponse:
    """Get parameters for node choice."""
    if not await AppCenterManager.validate_user_app_access(request.state.user_id, appId):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=jsonable_encoder(
                GetParamsRsp(
                    code=status.HTTP_403_FORBIDDEN,
                    message="用户没有权限访问该流",
                    result=[],
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    flow = await FlowManager.get_flow_by_app_and_flow_id(appId, flowId)
    if not flow:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=jsonable_encoder(
                GetParamsRsp(
                    code=status.HTTP_404_NOT_FOUND,
                    message="未找到该流",
                    result=[],
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    result = await ParameterManager.get_pre_params_by_flow_and_step_id(flow, stepId)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetParamsRsp(
                code=status.HTTP_200_OK,
                message="获取参数成功",
                result=result,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )


@router.get("/operate", response_model=GetOperaRsp)
async def get_operate_parameters(paramType: Type) -> JSONResponse:  # noqa: N803
    """Get parameters for node choice."""
    result = await ParameterManager.get_operate_and_bind_type(paramType)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            GetOperaRsp(
                code=status.HTTP_200_OK,
                message="获取操作成功",
                result=result,
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
