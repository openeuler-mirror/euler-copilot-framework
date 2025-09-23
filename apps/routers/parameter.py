from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user
from apps.dependency.user import verify_user
from apps.services.parameter import ParameterManager
from apps.schemas.response_data import (
    GetOperaRsp,
    GetParamsRsp
)
from apps.services.application import AppManager
from apps.services.flow import FlowManager

router = APIRouter(
    prefix="/api/parameter",
    tags=["parameter"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get("", response_model=GetParamsRsp)
async def get_parameters(
    user_sub: Annotated[str, Depends(get_user)],
    app_id: Annotated[str, Query(alias="appId")],
    flow_id: Annotated[str, Query(alias="flowId")],
    step_id: Annotated[str, Query(alias="stepId")],
) -> JSONResponse:
    """Get parameters for node choice."""
    if not await AppManager.validate_user_app_access(user_sub, app_id):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=GetParamsRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=[],
            ).model_dump(exclude_none=True, by_alias=True),
        )
    flow = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
    if not flow:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=GetParamsRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="未找到该流",
                result=[],
            ).model_dump(exclude_none=True, by_alias=True),
        )
    result = await ParameterManager.get_pre_params_by_flow_and_step_id(flow, step_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetParamsRsp(
            code=status.HTTP_200_OK,
            message="获取参数成功",
            result=result
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/operate", response_model=GetOperaRsp)
async def get_operate_parameters(
    user_sub: Annotated[str, Depends(get_user)],
    param_type: Annotated[str, Query(alias="ParamType")],
) -> JSONResponse:
    """Get parameters for node choice."""
    result = await ParameterManager.get_operate_and_bind_type(param_type)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetOperaRsp(
            code=status.HTTP_200_OK,
            message="获取操作成功",
            result=result
        ).model_dump(exclude_none=True, by_alias=True),
    )
