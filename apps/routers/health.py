"""FastAPI 健康检查接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from apps.entities.response_data import HealthCheckRsp

router = APIRouter(
    prefix="/health_check",
    tags=["health_check"],
)


@router.get("", response_model=HealthCheckRsp)
def health_check():  # noqa: ANN201
    """健康检查接口"""
    return JSONResponse(status_code=status.HTTP_200_OK, content=HealthCheckRsp(
        status="ok",
    ).model_dump(exclude_none=True, by_alias=True))
