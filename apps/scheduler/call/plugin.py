# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""API插件Call"""

from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from apps.scheduler.call.core import CoreCall, DataBase
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.scheduler import CallInfo, CallOutputChunk, CallVars


class Plugin(CoreCall, input_model=DataBase, output_model=DataBase):
    """API插件Call"""
    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "API插件节点",
            "type": CallType.DEFAULT,
            "description": "API插件节点，用于调用外部API服务",
        },
        LanguageType.ENGLISH: {
            "name": "API Plugin Node",
            "type": CallType.DEFAULT,
            "description": "API Plugin node for calling external API services",
        },
    }

    async def _init(self, call_vars: CallVars) -> DataBase:
        """
        初始化Call

        :param CallVars call_vars: 由Executor传入的变量，包含当前运行信息
        :return: Call的输入
        :rtype: DataBase
        """
        return DataBase()


    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """
        执行Call

        :param dict[str, Any] input_data: 填充后的Call的最终输入
        :return: Call的输出
        :rtype: AsyncGenerator[CallOutputChunk, None]
        """
        # API插件节点的执行逻辑
        # 这里可以根据serviceId调用相应的API服务
        # 目前先返回空结果，表示插件不可用
        output = CallOutputChunk(
            type=CallOutputType.DATA, 
            content={
                "message": "API插件节点不可用，请检查插件配置",
                "status": "unavailable"
            }
        )
        yield output
