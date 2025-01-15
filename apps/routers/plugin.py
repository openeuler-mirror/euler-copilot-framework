"""FastAPI 插件信息接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_user
from apps.entities.response_data import GetPluginListMsg, GetPluginListRsp
from apps.scheduler.pool.pool import Pool

router = APIRouter(
    prefix="/api/plugin",
    tags=["plugin"],
    dependencies=[
        Depends(verify_user),
    ],
)


# 前端展示插件详情
@router.get("", response_model=GetPluginListRsp)
async def get_plugin_list():  # noqa: ANN201
    """获取插件列表"""
    plugins = Pool().get_plugin_list()
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetPluginListRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=GetPluginListMsg(plugins=plugins),
        ).model_dump(exclude_none=True, by_alias=True),
    )

# TODO(zwt): 热重载插件
# 004
# @router.post("")
# async def reload_plugin():
#     pass
