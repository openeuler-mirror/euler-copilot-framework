"""ChromaDB内存向量数据库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from typing import ClassVar, Optional

import numpy as np
import requests
from chromadb import (
    Client,
    Collection,
    Documents,
    EmbeddingFunction,
    Embeddings,
)
from chromadb.api import ClientAPI
from chromadb.api.types import IncludeEnum
from pydantic import BaseModel, Field

from apps.common.config import config
from apps.constants import LOGGER


def _get_embedding(text: list[str]) -> list[np.ndarray]:
    """访问Vectorize的Embedding API，获得向量化数据

    :param text: 待向量化文本（多条文本组成List）
    :return: 文本对应的向量（顺序与text一致，也为List）
    """
    api = config["EMBEDDING_URL"].rstrip("/") + "/embeddings"

    headers = {
        "Authorization": f"Bearer {config['EMBEDDING_KEY']}",
    }
    data = {
       "encoding_format": "float",
       "input": text,
       "model": config["EMBEDDING_MODEL"],
    }

    response = requests.post(
        api,
        json=data,
        headers=headers,
        verify=False,  # noqa: S501
        timeout=30,
    )

    return [np.array(item["embedding"]) for item in response.json()["data"]]


# 模块内部类，不应在模块外部使用
class DocumentWrapper(BaseModel):
    """单个ChromaDB文档的结构"""

    data: str = Field(description="文档内容")
    id: str = Field(description="文档ID，用于确保唯一性")
    metadata: Optional[dict] = Field(description="文档元数据", default=None)


class RAGEmbedding(EmbeddingFunction):
    """ChromaDB用于进行文本向量化的函数"""

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        """调用RAG接口进行文本向量化"""
        return _get_embedding(input)


class VectorDB:
    """ChromaDB单例"""

    client: ClassVar[ClientAPI] = Client()

    @classmethod
    def get_collection(cls, collection_name: str) -> Optional[Collection]:
        """创建并返回ChromaDB集合

        :param collection_name: 集合名称，字符串
        :return: ChromaDB集合对象
        """
        try:
            return cls.client.get_or_create_collection(collection_name, embedding_function=RAGEmbedding(),
                                                       metadata={"hnsw:space": "cosine"})
        except Exception as e:
            LOGGER.error(f"Get collection failed: {e}")
            return None

    @classmethod
    def delete_collection(cls, collection_name: str) -> None:
        """删除ChromaDB集合

        :param collection_name: 集合名称，字符串
        """
        cls.client.delete_collection(collection_name)

    @classmethod
    def add_docs(cls, collection: Collection, docs: list[DocumentWrapper]) -> None:
        """向ChromaDB集合中添加文档

        :param collection: ChromaDB集合对象
        :param docs: 待向量化的文档List
        """
        doc_list = []
        metadata_list = []
        id_list = []
        for doc in docs:
            doc_list.append(doc.data)
            id_list.append(doc.id)
            metadata_list.append(doc.metadata)

        collection.add(
            ids=id_list,
            metadatas=metadata_list,
            documents=doc_list,
        )

    @classmethod
    def get_docs(cls, collection: Collection, question: str, requirements: dict, num: int = 3) -> list[DocumentWrapper]:
        """根据输入，从ChromaDB中查询K个向量最相似的文档

        :param collection: ChromaDB集合对象
        :param question: 查询输入
        :param requirements: 查询过滤条件
        :param num: Top K中K的值
        :return: 文档List，包含文档内容、元数据、ID
        """
        result = collection.query(
            query_texts=[question],
            where=requirements,
            n_results=num,
            include=[IncludeEnum.documents, IncludeEnum.metadatas],
        )

        length = min(num, len(result["ids"][0]))
        return [
            DocumentWrapper(
                id=result["ids"][0][i],
                metadata=result["metadatas"][0][i],  # type: ignore[index]
                data=result["documents"][0][i],  # type: ignore[index]
            )
            for i in range(length)
        ]
