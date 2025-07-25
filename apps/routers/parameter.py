from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user
from apps.dependency.user import verify_user
from apps.scheduler.call.choice.choice import Choice
from apps.schemas.response_data import (
    FlowStructureGetMsg,
    FlowStructureGetRsp,
    GetParamsMsg,
    GetParamsRsp,
    ResponseData,
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


@router.get("", response_model={
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },)
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
            content=FlowStructureGetRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=FlowStructureGetMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    flow = await FlowManager.get_flow_by_app_and_flow_id(app_id, flow_id)
    if not flow:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=FlowStructureGetRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="未找到该流",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    result = await FlowManager.get_params_by_flow_and_step_id(flow, step_id)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=FlowStructureGetRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="未找到该节点",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetParamsRsp(
            code=status.HTTP_200_OK,
            message="获取参数成功",
            result=GetParamsMsg(result=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )

async def operate_parameters(operate: str) -> list[str] | None:
    """
    根据操作类型获取对应的操作符参数列表

    Args:
        operate: 操作类型，支持 'int', 'str', 'bool'

    Returns:
        对应的操作符参数列表，若类型不支持则返回None

    """
    string = [
        "equal",
        "not_equal",
        "great",#长度大于
        "great_equals",#长度大于等于
        "less",#长度小于
        "less_equals",#长度小于等于
        "greater",
        "greater_equals",
        "smaller",
        "smaller_equals",
    ]
    integer = [
        "equal",
        "not_equal",
        "great",
        "great_equals",
        "less",
        "less_equals",
    ]
    boolen = ["equal", "not_equal", "is_empty", "not_empty"]
    if operate in string:
        return string
    if operate in integer:
        return integer
    if operate in boolen:
        return boolen
    return None

@router.get("/operate", response_model={
    status.HTTP_200_OK: {"model": ResponseData},
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },)
async def get_operate_parameters(
    user_sub: Annotated[str, Depends(get_user)],
    operate: Annotated[str, Query(alias="operate")],
) -> JSONResponse:
    """Get parameters for node choice."""
    result = await operate_parameters(operate)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ResponseData(
                code=status.HTTP_404_NOT_FOUND,
                message="未找到该符号",
                result=[],
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="获取参数成功",
            result=result,
        ).model_dump(exclude_none=True, by_alias=True),
    )