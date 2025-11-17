# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP节点基类"""

import logging

from anyio import Path

from apps.llm import LLM
from apps.models import LanguageType

logger = logging.getLogger(__name__)


class MCPNodeBase:
    """MCP节点基类"""

    def __init__(self, llm: LLM, language: LanguageType = LanguageType.CHINESE) -> None:
        """初始化MCP节点基类"""
        self._llm = llm
        self._language = language

    async def _load_prompt(self, prompt_id: str) -> str:
        """
        从Markdown文件加载提示词

        :param prompt_id: 提示词ID，例如 "mcp_select", "gen_params" 等
        :return: 提示词内容
        """
        # 组装Prompt文件路径: prompt_id.language.md (例如: mcp_select.zh.md)
        filename = f"{prompt_id}.{self._language.value}.md"
        prompt_dir = Path(__file__).parent.parent.parent / "data" / "prompts" / "system" / "mcp"
        prompt_file = prompt_dir / filename
        return await prompt_file.read_text(encoding="utf-8")
