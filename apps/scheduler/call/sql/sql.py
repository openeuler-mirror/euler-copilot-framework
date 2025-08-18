# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""SQL工具"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

import httpx
from fastapi import status
from pydantic import Field

from apps.common.config import Config
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.sql.schema import SQLInput, SQLOutput
from apps.schemas.enum_var import CallOutputType, LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)

MESSAGE = {
    "invaild": {
        LanguageType.CHINESE: "SQL查询错误：无法生成有效的SQL语句！",
        LanguageType.ENGLISH: "SQL query error: Unable to generate valid SQL statements!",
    },
    "fail": {
        LanguageType.CHINESE: "SQL查询错误：SQL语句执行失败！",
        LanguageType.ENGLISH: "SQL query error: SQL statement execution failed!",
    },
}


class SQL(CoreCall, input_model=SQLInput, output_model=SQLOutput):
    """SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。"""

    database_url: str = Field(description="数据库连接地址")
    table_name_list: list[str] = Field(description="表名列表",default=[])
    top_k: int = Field(description="生成SQL语句数量",default=5)
    use_llm_enhancements: bool = Field(description="是否使用大模型增强", default=False)

    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "SQL查询",
            "description": "使用大模型生成SQL语句，用于查询数据库中的结构化数据",
        },
        LanguageType.ENGLISH: {
            "name": "SQL Query",
            "description": "Use the foundation model to generate SQL statements to query structured data in the databases",
        },
    }

    async def _init(self, call_vars: CallVars) -> SQLInput:
        """初始化SQL工具。"""
        return SQLInput(
            question=call_vars.question,
        )


    async def _generate_sql(self, data: SQLInput) -> list[dict[str, Any]]:
        """生成SQL语句列表"""
        post_data = {
            "database_url": self.database_url,
            "table_name_list": self.table_name_list,
            "question": data.question,
            "topk": self.top_k,
            "use_llm_enhancements": self.use_llm_enhancements,
        }
        headers = {"Content-Type": "application/json"}

        sql_list = []
        request_num = 0
        max_request = 5

        while request_num < max_request and len(sql_list) < self.top_k:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        Config().get_config().extra.sql_url + "/database/sql",
                        headers=headers,
                        json=post_data,
                        timeout=60.0,
                    )
                    request_num += 1
                    if response.status_code == status.HTTP_200_OK:
                        result = response.json()
                        if result["code"] == status.HTTP_200_OK:
                            sql_list.extend(result["result"]["sql_list"])
                    else:
                        logger.error("[SQL] 生成失败：%s", response.text)
            except Exception:
                logger.exception("[SQL] 生成失败")
                request_num += 1

        return sql_list


    async def _execute_sql(
        self,
        sql_list: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        """执行SQL语句并返回结果"""
        headers = {"Content-Type": "application/json"}

        for sql_dict in sql_list:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        Config().get_config().extra.sql_url + "/sql/execute",
                        headers=headers,
                        json={
                            "database_id": sql_dict["database_id"],
                            "sql": sql_dict["sql"],
                        },
                        timeout=60.0,
                    )
                    if response.status_code == status.HTTP_200_OK:
                        result = response.json()
                        if result["code"] == status.HTTP_200_OK:
                            return result["result"], sql_dict["sql"]
                    else:
                        logger.error("[SQL] 调用失败：%s", response.text)
            except Exception:
                logger.exception("[SQL] 调用失败")

        return None, None

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """运行SQL工具"""  
        data = SQLInput(**input_data)

        # 生成SQL语句
        sql_list = await self._generate_sql(data)
        if not sql_list:
            raise CallError(
                message=MESSAGE["invaild"][language],
                data={},
            )

        # 执行SQL语句
        sql_exec_results, sql_exec = await self._execute_sql(sql_list)
        if sql_exec_results is None or sql_exec is None:
            raise CallError(
                message=MESSAGE["fail"][language],
                data={},
            )

        # 返回结果
        data = SQLOutput(
            dataset=sql_exec_results,
            sql=sql_exec,
        ).model_dump(exclude_none=True, by_alias=True)

        yield CallOutputChunk(
            content=data,
            type=CallOutputType.DATA,
        )
