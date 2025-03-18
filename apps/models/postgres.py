"""向postgresql中存储向量化数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

import aiohttp
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.common.config import config
from apps.entities.vector import Base


class PostgreSQL:
    """PostgreSQL向量化存储"""

    _engine = create_async_engine(
        f"postgresql+asyncpg://{config['POSTGRES_USER']}:{config['POSTGRES_PWD']}@{config['POSTGRES_HOST']}/{config['POSTGRES_DATABASE']}",
        echo=True,
        pool_recycle=300,
        pool_pre_ping=True,
    )
    _is_inited = False

    @classmethod
    async def init(cls) -> None:
        """初始化PostgreSQL"""
        if cls._is_inited:
            return
        cls._is_inited = True
        async with cls._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @classmethod
    async def get_session(cls) -> AsyncSession:
        """获取异步会话"""
        if not cls._is_inited:
            await cls.init()
        return async_sessionmaker(cls._engine, class_=AsyncSession, expire_on_commit=False)()


    @staticmethod
    async def _get_openai_embedding(text: list[str]) -> list[list[float]]:
        """访问OpenAI兼容的Embedding API，获得向量化数据"""
        api = config["EMBEDDING_URL"] + "/v1/embeddings"
        data = {
            "input": text,
            "model": config["EMBEDDING_MODEL"],
            "encoding_format": "float",
        }

        headers = {
            "Content-Type": "application/json",
        }
        if config["EMBEDDING_KEY"]:
            headers["Authorization"] = f"Bearer {config['EMBEDDING_KEY']}"

        async with aiohttp.ClientSession() as session, session.post(
            api, json=data, headers=headers, timeout=60,
        ) as response:
            json = await response.json()
            return [item["embedding"] for item in json["data"]]


    @staticmethod
    async def _get_tei_embedding(text: list[str]) -> list[list[float]]:
        """访问TEI兼容的Embedding API，获得向量化数据"""
        api = config["EMBEDDING_URL"] + "/embed"
        headers = {
            "Content-Type": "application/json",
        }
        if config["EMBEDDING_KEY"]:
            headers["Authorization"] = f"Bearer {config['EMBEDDING_KEY']}"

        session = aiohttp.ClientSession()

        result = []
        for single_text in text:
            data = {
                "inputs": single_text,
                "normalize": True,
            }
            async with session.post(api, json=data, headers=headers, timeout=60) as response:
                json = await response.json()
                result.append(json[0])

        await session.close()
        return result



    @staticmethod
    async def get_embedding(text: list[str]) -> list[list[float]]:
        """访问OpenAI兼容的Embedding API，获得向量化数据

        :param text: 待向量化文本（多条文本组成List）
        :return: 文本对应的向量（顺序与text一致，也为List）
        """
        if config["EMBEDDING_TYPE"] == "openai":
            return await PostgreSQL._get_openai_embedding(text)
        if config["EMBEDDING_TYPE"] == "mindie":
            return await PostgreSQL._get_tei_embedding(text)

        err = f"不支持的Embedding API类型: {config['EMBEDDING_TYPE']}"
        raise ValueError(err)
