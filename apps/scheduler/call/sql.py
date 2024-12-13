# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from typing import Dict, Any, Union
import aiohttp
import json
from sqlalchemy import create_engine, Engine, text
import logging

from apps.scheduler.call.core import CoreCall, CallParams
from apps.common.config import config
from apps.scheduler.encoder import JSONSerializer


logger = logging.getLogger('gunicorn.error')


class SQL(CoreCall):
    """
    SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。
    """

    name: str = "sql"
    description: str = "SQL工具，用于查询数据库中的结构化数据"
    params_obj: CallParams

    session: aiohttp.ClientSession
    engine: Engine

    def __init__(self, params: Dict[str, Any]):
        """
        初始化SQL工具。
        解析SQL工具参数，拼接PostgreSQL连接字符串，创建SQLAlchemy Engine。
        :param params: SQL工具需要的参数。
        """
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(300))
        self.params_obj = CallParams(**params)

        db_url = f'postgresql+psycopg2://{config["POSTGRES_USER"]}:{config["POSTGRES_PWD"]}@{config["POSTGRES_HOST"]}/{config["POSTGRES_DATABASE"]}'
        self.engine = create_engine(db_url, pool_size=20, max_overflow=80, pool_recycle=300, pool_pre_ping=True)


    async def call(self, fixed_params: Union[Dict[str, Any], None] = None) -> Dict[str, Any]:
        """
        运行SQL工具。
        访问Chat2DB工具API，拿到针对用户输入的最多5条SQL语句。依次尝试每一条语句，直到查询出数据或全部不可用。
        :param fixed_params: 经用户确认后的参数（目前未使用）
        :return: 从数据库中查询得到的数据，或报错信息
        """
        post_data = {
            "question": self.params_obj.question,
            "topk_sql": 5,
            "use_llm_enhancements": True
        }
        headers = {
            "Content-Type": "application/json"
        }

        async with self.session.post(config["SQL_URL"], ssl=False, json=post_data, headers=headers) as response:
            if response.status != 200:
                return {
                    "output": "",
                    "message": "SQL查询错误：API返回状态码{}, 详细原因为{}，附加信息为{}。".format(response.status, response.reason, await response.text())
                }
            else:
                result = json.loads(await response.text())
                logger.info(f"SQL工具返回的信息为：{result}")
                
        await self.session.close()
        for item in result["sql_list"]:
            try:
                with self.engine.connect() as connection:
                    db_result = connection.execute(text(item["sql"])).all()
                    dataset_list = []
                    for db_item in db_result:
                        dataset_list.append(db_item._asdict())
                    return {
                        "output": json.dumps(dataset_list, cls=JSONSerializer, ensure_ascii=False),
                        "message": "数据库查询成功！"
                    }
            except Exception:
                continue

        raise ValueError("数据库查询出现错误！")
