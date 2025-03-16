"""SQL工具。

用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
import logging
from typing import Any, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field
from sqlalchemy import text

from apps.common.config import config
from apps.entities.scheduler import CallError, CallVars
from apps.models.postgres import PostgreSQL
from apps.scheduler.call.core import CoreCall

logger = logging.getLogger("ray")


class SQLOutput(BaseModel):
    """SQL工具的输出"""

    messages: list[str] = Field(description="SQL工具的执行结果列表")


class SQL(CoreCall):
    """SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。"""

    name: str = "数据库"
    description: str = "使用大模型生成SQL语句，用于查询数据库中的结构化数据"
    message: str = Field(description="SQL工具的执行结果")
    database_id: str = Field(description="数据库的id", alias="db_sn", default=None)
    table_id_list: Optional[list[str]] = Field(description="表id列表", default=[])
    top_k: int = Field(description="返回的答案数量", default=1)
    use_llm_enhancements: Optional[bool] = Field(description="是否使用大模型增强", default=False)

    def init(self, _syscall_vars: CallVars, **_kwargs) -> dict[str, Any]:
        """初始化SQL工具。"""
        # 初始化aiohttp的ClientSession
        self._params_dict = {
            "database_id": self.database_id,
            "table_id_list": self.table_id_list,
            "topk": self.top_k,
            "use_llm_enhancements": self.use_llm_enhancements,
            "question": _syscall_vars.question,
        }

        self._generate_url = config["CHAT2DB_HOST"].rstrip("/") + "/sql/generate"
        self._execute_url = config["CHAT2DB_HOST"].rstrip("/") + "/sql/execute"
        self._headers = {
            "Content-Type": "application/json",
        }

        return self._params_dict

    async def exec(self) -> SQLOutput:
        """运行SQL工具"""
        # 获取必要参数
        sql_list = []
        retry = 0
        max_retry = 3
        while retry < max_retry:
            async with aiohttp.ClientSession() as session, session.post(self._generate_url, headers=self._headers, json=self._params_dict) as response:
                # 检查响应状态码
                if response.status == status.HTTP_200_OK:
                    result = await response.json()
                    sub_sql_list = result['result']['sql_list']
                    sql_list += sub_sql_list
                else:
                    text = await response.text()
                    logger.error("[SQL] 调用失败：%s", text)
                    continue
            if len(sql_list) >= self._params_dict['topk']:
                break
            retry += 1
        sql_exec_results = []
        for sql_dict in sql_list:
            database_id = sql_dict['database_id']
            sql = sql_dict['sql']
            data = {
                'database_id': database_id,
                'sql': sql
            }
            async with aiohttp.ClientSession() as session, session.post(self._execute_url, headers=self._headers, json=data) as response:
                # 检查响应状态码
                if response.status == status.HTTP_200_OK:
                    result = await response.json()
                    sql_exec_result = result['result']
                    sql_exec_results.append(sql_exec_result)
                else:
                    text = await response.text()
                    logger.error("[SQL] 调用失败：%s", text)
                    continue
        if len(sql_exec_results) >= self._params_dict['topk']:
            return SQLOutput(
                messages=sql_exec_results,
            ).model_dump(exclude_none=True, by_alias=True)
        raise CallError(
            message="SQL查询错误：SQL语句错误，数据库查询失败！",
            data={},
        )
