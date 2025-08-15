"""搜索工具"""

from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.search.schema import SearchInput, SearchOutput
from apps.schemas.enum_var import LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)


class Search(CoreCall, input_model=SearchInput, output_model=SearchOutput):
    """搜索工具"""

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "搜索",
            "description": "获取搜索引擎的结果。",
        },
        LanguageType.ENGLISH: {
            "name": "Search",
            "description": "Get the results of the search engine.",
        },
    }

    @classmethod
    def info(cls) -> CallInfo:
        """
        返回Call的名称和描述

        :return: Call的名称和描述
        :rtype: CallInfo
        """
        lang_info = cls.i18n_info.get(cls.language, cls.i18n_info[LanguageType.CHINESE])
        return CallInfo(name=lang_info["name"], description=lang_info["description"])

    async def _init(self, call_vars: CallVars) -> SearchInput:
        """初始化工具"""
        pass


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        pass

