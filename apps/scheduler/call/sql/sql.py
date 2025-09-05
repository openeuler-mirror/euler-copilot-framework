# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""SQL工具"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from urllib.parse import urlparse
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

    database_type: str = Field(description="数据库类型",default="postgres") # mysql mongodb opengauss postgres
    host: str = Field(description="数据库地址",default="localhost")
    port: int = Field(description="数据库端口",default=5432)
    username: str = Field(description="数据库用户名",default="root")
    password: str = Field(description="数据库密码",default="root")
    database: str = Field(description="数据库名称",default="postgres")

    table_name_list: list[str] = Field(description="表名列表",default=[])



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

    async def _exec(
        self, input_data: dict[str, Any], language: LanguageType = LanguageType.CHINESE
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """运行SQL工具, 支持MySQL, MongoDB, PostgreSQL, OpenGauss"""

        data = SQLInput(**input_data)

        headers = {"Content-Type": "application/json"}

        post_data = {
            "type": self.database_type, 
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            "goal": data.question,
            "table_list": self.table_name_list,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    Config().get_config().extra.sql_url + "/sql/handler",
                    headers=headers,
                    json=post_data,
                    timeout=60.0,
                )

                result = response.json()
                if response.status_code == status.HTTP_200_OK:
                    if result["code"] == status.HTTP_200_OK:
                        result_data = result["result"]
                        sql_exec_results = result_data.get("execute_result")
                        sql_exec = result_data.get("sql")
                        sql_exec_risk = result_data.get("risk")
                        logger.info("[SQL] 调用成功\n[SQL 语句]: %s\n[SQL 结果]: %s\n[SQL 风险]: %s", sql_exec, sql_exec_results, sql_exec_risk)

                else:
                    logger.error("[SQL] 调用失败：%s", response.text)
                    logger.error("[SQL] 错误信息：%s", response["result"])
        except Exception:
            logger.exception("[SQL] 调用失败")



        # 返回结果
        data = SQLOutput(
            result=sql_exec_results,
            sql=sql_exec,
        ).model_dump(exclude_none=True, by_alias=True)

        yield CallOutputChunk(
            content=data,
            type=CallOutputType.DATA,
        )
