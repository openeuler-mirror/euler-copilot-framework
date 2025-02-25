"""SQL工具。

用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any, Optional

import aiohttp
from fastapi import status
from pydantic import BaseModel, Field
from sqlalchemy import text

from apps.common.config import config
from apps.constants import LOGGER
from apps.entities.scheduler import CallError, CallVars
from apps.models.postgres import PostgreSQL
from apps.scheduler.call.core import CoreCall


class SQLOutput(BaseModel):
    """SQL工具的输出"""

    message: str = Field(description="SQL工具的执行结果")
    dataset: list[dict[str, Any]] = Field(description="SQL工具的执行结果")


class SQL(CoreCall):
    """SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。"""

    name: str = "数据库"
    description: str = "使用大模型生成SQL语句，用于查询数据库中的结构化数据"
    sql: Optional[str] = Field(description="用户输入")


    def init(self, _syscall_vars: CallVars, **_kwargs) -> None:  # noqa: ANN003
        """初始化SQL工具。"""
        # 初始化aiohttp的ClientSession
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(300))


    async def __call__(self, _slot_data: dict[str, Any]) -> SQLOutput:
        """运行SQL工具"""
        # 获取必要参数
        syscall_vars: CallVars = getattr(self, "_syscall_vars")

        # 若手动设置了SQL，则直接使用
        session = await PostgreSQL.get_session()
        if params.sql:
            try:
                result = (await session.execute(text(params.sql))).all()
                await session.close()

                dataset_list = [db_item._asdict() for db_item in result]
                return SQLOutput(
                    message="SQL查询成功！",
                    dataset=dataset_list,
                )
            except Exception as e:
                raise CallError(message=f"SQL查询错误：{e!s}", data={}) from e

        # 若未设置SQL，则调用Chat2DB工具API，获取SQL
        post_data = {
            "question": syscall_vars.question,
            "topk_sql": 5,
            "use_llm_enhancements": True,
        }
        headers = {
            "Content-Type": "application/json",
        }

        async with self._session.post(config["SQL_URL"], ssl=False, json=post_data, headers=headers) as response:
            if response.status != status.HTTP_200_OK:
                raise CallError(
                    message=f"SQL查询错误：API返回状态码{response.status}, 详细原因为{response.reason}。",
                    data={"response": await response.text()},
                )
            result = json.loads(await response.text())
            LOGGER.info(f"SQL工具返回的信息为：{result}")
        await self._session.close()

        for item in result["sql_list"]:
            try:
                db_result = (await session.execute(text(item["sql"]))).all()
                await session.close()

                dataset_list = [db_item._asdict() for db_item in db_result]
                return SQLOutput(
                    message="数据库查询成功！",
                    dataset=dataset_list,
                )
            except Exception as e:  # noqa: PERF203
                LOGGER.error(f"SQL查询错误，错误信息为：{e}，正在换用下一条SQL语句。")

        raise CallError(
            message="SQL查询错误：SQL语句错误，数据库查询失败！",
            data={},
        )
