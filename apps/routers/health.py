# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from fastapi import APIRouter, Response, status

router = APIRouter(
    prefix="/health_check",
    tags=["health_check"]
)


@router.get("")
def health_check():
    return Response(status_code=status.HTTP_200_OK, content="ok")
