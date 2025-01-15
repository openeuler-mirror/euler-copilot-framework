"""SQL工具。

用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Any

import aiohttp
from fastapi import status
from sqlalchemy import create_engine, text

from apps.common.config import config
from apps.constants import LOGGER
from apps.entities.plugin import CallError, CallResult, SysCallVars
from apps.scheduler.call.core import CoreCall


class SQL(CoreCall):
    """SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。"""

    name: str = "sql"
    description: str = "SQL工具，用于查询数据库中的结构化数据"


    async def init(self, syscall_vars: SysCallVars, **kwargs) -> None:  # noqa: ANN003
        """初始化SQL工具。"""
        await super().init(syscall_vars, **kwargs)
        # 初始化aiohttp的ClientSession
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(300))
        # 初始化SQLAlchemy Engine
        try:
            db_url = f'postgresql+psycopg2://{config["POSTGRES_USER"]}:{config["POSTGRES_PWD"]}@{config["POSTGRES_HOST"]}/{config["POSTGRES_DATABASE"]}'
            self._engine = create_engine(db_url, pool_size=20, max_overflow=80, pool_recycle=300, pool_pre_ping=True)
        except Exception as e:
            raise CallError(message=f"数据库连接失败：{e!s}", data={}) from e


    async def call(self, _slot_data: dict[str, Any]) -> CallResult:
        """运行SQL工具。

        访问Chat2DB工具API，拿到针对用户输入的最多5条SQL语句。依次尝试每一条语句，直到查询出数据或全部不可用。
        :param slot_data: 经用户确认后的参数（目前未使用）
        :return: 从数据库中查询得到的数据，或报错信息
        """
        post_data = {
            "question": self._syscall_vars.question,
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
                with self._engine.connect() as connection:
                    db_result = connection.execute(text(item["sql"])).all()
                    dataset_list = [db_item._asdict() for db_item in db_result]
                    return CallResult(
                        output={
                            "dataset": dataset_list,
                        },
                        output_schema={
                            "dataset": {
                                "type": "array",
                                "description": "数据库查询结果",
                                "items": {
                                    "type": "object",
                                    "description": "数据库查询结果的每一行",
                                },
                            },
                        },
                        message="数据库查询成功！",
                    )
            except Exception as e:  # noqa: PERF203
                LOGGER.error(f"SQL查询错误，错误信息为：{e}，正在换用下一条SQL语句。")

        raise CallError(
            message="SQL查询错误：SQL语句错误，数据库查询失败！",
            data={},
        )
