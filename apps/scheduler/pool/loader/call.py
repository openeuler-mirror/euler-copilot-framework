# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Call 加载器"""

import importlib
import logging

from sqlalchemy import delete, inspect

from apps.common.postgres import postgres
from apps.llm import embedding
from apps.models import NodeInfo
from apps.schemas.scheduler import CallInfo

_logger = logging.getLogger(__name__)


async def _table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    async with postgres.engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(table_name),
        )


class CallLoader:
    """Call 加载器"""

    async def _load_system_call(self) -> dict[str, CallInfo]:
        """加载系统Call"""
        call_metadata = {}

        # 动态导入 apps.scheduler.call 模块
        system_call = importlib.import_module("apps.scheduler.call")

        # 检查合法性
        for call_id in system_call.__all__:
            call_cls = getattr(system_call, call_id)
            call_info = call_cls.info()
            call_metadata[call_id] = call_info

        return call_metadata


    # 将数据插入数据库
    async def _add_data_to_db(self, call_metadata: dict[str, CallInfo]) -> None:
        """将数据插入数据库"""
        # 清除旧数据
        async with postgres.session() as session:
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == None))  # noqa: E711

            # 更新数据库
            call_descriptions = []
            for call_id, call in call_metadata.items():
                await session.merge(NodeInfo(
                    id=call_id,
                    name=call.name,
                    description=call.description,
                    serviceId=None,
                    callId=call_id,
                    knownParams={},
                    overrideInput={},
                    overrideOutput={},
                ))
                call_descriptions.append(call.description)

            await session.commit()


    async def _add_vector_to_db(self, call_metadata: dict[str, CallInfo]) -> None:
        """将向量化数据存入数据库"""
        # 检查表是否存在
        if not await _table_exists(embedding.NodePoolVector.__tablename__):
            _logger.warning(
                "表 %s 不存在，跳过向量数据插入",
                embedding.NodePoolVector.__tablename__,
            )
            return

        async with postgres.session() as session:
            # 删除旧数据
            await session.execute(
                delete(embedding.NodePoolVector).where(embedding.NodePoolVector.serviceId == None),  # noqa: E711
            )

            call_vecs = await embedding.get_embedding([call.description for call in call_metadata.values()])
            for call_id, vec in zip(call_metadata.keys(), call_vecs, strict=True):
                session.add(embedding.NodePoolVector(
                    id=call_id,
                    embedding=vec,
                ))
            await session.commit()


    async def set_vector(self) -> None:
        """将向量化数据存入数据库"""
        call_metadata = await self._load_system_call()
        await self._add_vector_to_db(call_metadata)


    async def load(self) -> None:
        """初始化Call信息"""
        # 载入所有已知的Call信息
        try:
            sys_call_metadata = await self._load_system_call()
        except Exception as e:
            err = "[CallLoader] 载入系统Call信息失败"
            _logger.exception(err)
            raise RuntimeError(err) from e

        # 更新数据库
        await self._add_data_to_db(sys_call_metadata)
