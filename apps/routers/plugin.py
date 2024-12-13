# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from fastapi import APIRouter, Depends, status

from apps.dependency.user import verify_user
from apps.entities.plugin import PluginData, PluginListData
from apps.scheduler.pool.pool import Pool

router = APIRouter(
    prefix="/api/plugin",
    tags=["plugin"],
    dependencies=[
        Depends(verify_user)
    ]
)


# 前端展示插件详情
@router.get("", response_model=PluginListData)
async def get_plugin_list():
    plugins = Pool().get_plugin_list()
    return PluginListData(code=status.HTTP_200_OK, message="success", result=plugins)
