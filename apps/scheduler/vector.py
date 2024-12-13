# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from typing import List, Optional

import chromadb
from chromadb import Documents, Embeddings, EmbeddingFunction, Collection
from pydantic import BaseModel, Field
import requests
import logging

from apps.common.config import config


logger = logging.getLogger('gunicorn.error')


def get_embedding(text: List[str]):
    """
    访问Vectorize的Embedding API，获得向量化数据
    :param text: 待向量化文本（多条文本组成List）
    :return: 文本对应的向量（顺序与text一致，也为List）
    """

    api = config["VECTORIZE_HOST"].rstrip("/") + "/embedding"
    response = requests.post(
        api, 
        json={"texts": text}
    )

    return response.json()


# 模块内部类，不应在模块外部使用
class DocumentWrapper(BaseModel):
    """
    单个ChromaDB文档的结构
    """
    data: str = Field(description="文档内容")
    id: str = Field(description="文档ID，用于确保唯一性")
    metadata: Optional[dict] = Field(description="文档元数据", default=None)


class RAGEmbedding(EmbeddingFunction):
    """
    ChromaDB用于进行文本向量化的函数
    """
    def __call__(self, input: Documents) -> Embeddings:
        return get_embedding(input)


class VectorDB:
    """
    ChromaDB单例
    """
    client: chromadb.ClientAPI = chromadb.Client()

    def __init__(self):
        raise NotImplementedError("VectorDB不应被实例化")

    @classmethod
    def get_collection(cls, collection_name: str) -> Collection:
        """
        创建并返回ChromaDB集合
        :param collection_name: 集合名称，字符串
        :return: ChromaDB集合对象
        """

        try:
            return cls.client.get_or_create_collection(collection_name, embedding_function=RAGEmbedding(),
                                                       metadata={"hnsw:space": "cosine"})
        except Exception as e:
            logger.error(f"Get collection failed: {e}")

    @classmethod
    def delete_collection(cls, collection_name: str):
        """
        删除ChromaDB集合
        :param collection_name: 集合名称，字符串
        :return:
        """
        cls.client.delete_collection(collection_name)

    @classmethod
    def add_docs(cls, collection: Collection, docs: List[DocumentWrapper]):
        """
        向ChromaDB集合中添加文档
        :param collection: ChromaDB集合对象
        :param docs: 待向量化的文档List
        :return:
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
            documents=doc_list
        )

    @classmethod
    def get_docs(cls, collection: Collection, question: str, requirements: dict, num: int = 3) -> List[DocumentWrapper]:
        """
        根据输入，从ChromaDB中查询K个向量最相似的文档
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
            include=["documents", "metadatas"]
        )

        item_list = []
        length = min(num, len(result["ids"]))
        for i in range(length):
            item_list.append(DocumentWrapper(
                id=result["ids"][i],
                metadata=result["metadatas"][i],
                documents=result["documents"][i]
            ))

        return item_list
