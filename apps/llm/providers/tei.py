# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商：Text Embedding Inference"""

import logging

import httpx
from typing_extensions import override

from apps.models import LLMType

from .base import BaseProvider

_logger = logging.getLogger(__name__)


class TEIProvider(BaseProvider):
    """Text Embedding Inference"""

    @override
    def _check_type(self) -> None:
        """检查模型能力是否包含Embedding"""
        if LLMType.EMBEDDING not in self.config.llmType:
            err = "模型能力不包含Embedding"
            _logger.error(err)
            raise RuntimeError(err)

    def _validate_input(self, text: list[str]) -> list[str]:
        """验证待向量化文本格式是否正确"""
        if not text:
            err = "待向量化文本不能为空"
            _logger.error(err)
            raise ValueError(err)
        filtered_text = [t for t in text if t.strip() != ""]
        if not filtered_text:
            err = "待向量化文本全为空字符串"
            _logger.error(err)
            raise ValueError(err)
        return filtered_text

    @override
    def _init_client(self) -> None:
        """初始化模型API客户端"""
        # 初始化配置信息，供embedding方法使用
        self._api_url = self.config.baseUrl + "/embed"
        self._headers = {
            "Content-Type": "application/json",
        }
        if self.config.apiKey:
            self._headers["Authorization"] = f"Bearer {self.config.apiKey}"

    @override
    async def embedding(self, text: list[str]) -> list[list[float]]:
        """访问TEI兼容的Embedding API，获得向量化数据"""
        text = self._validate_input(text)
        async with httpx.AsyncClient(verify=False) as client:  # noqa: S501
            result = []
            for single_text in text:
                data = {
                    "inputs": single_text,
                    "normalize": True,
                }
                response = await client.post(
                    self._api_url, json=data, headers=self._headers, timeout=60.0,
                )
                json = response.json()
                result.append(json[0])

            return result
