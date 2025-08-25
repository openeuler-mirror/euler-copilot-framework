# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对接Euler Copilot RAG"""

from datetime import UTC, datetime
import json
import logging
from collections.abc import AsyncGenerator
import re
import httpx
from typing import Any
from fastapi import status

from apps.common.config import Config
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.llm.reasoning import ReasoningLLM
from apps.llm.token import TokenCalculator
from apps.schemas.collection import LLM
from apps.schemas.config import LLMConfig
from apps.schemas.enum_var import EventType, LanguageType
from apps.schemas.rag_data import RAGQueryReq
from apps.services.session import SessionManager

logger = logging.getLogger(__name__)


class RAG:
    """调用RAG服务，获取知识库答案"""

    system_prompt: str = "You are a helpful assistant."
    """系统提示词"""
    user_prompt: dict[LanguageType, str] = {
        LanguageType.CHINESE: r"""
        <instructions>
                你是openEuler社区的智能助手。请结合给出的背景信息, 回答用户的提问，并且基于给出的背景信息在相关句子后进行脚注。
                一个例子将在<example>中给出。
                上下文背景信息将在<bac_info>中给出。
                用户的提问将在<user_question>中给出。
                注意：
                1.输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息直接作答。
                2.脚注的格式为[[1]]，[[2]]，[[3]]等，脚注的内容为提供的文档的id。
                3.脚注只出现在回答的句子的末尾，例如句号、问号等标点符号后面。
                4.不要对脚注本身进行解释或说明。
                5.请不要使用<example></example>中的文档的id作为脚注。
        </instructions>
        <example>
            <bac_info>
                    <document id = 1 name = example_doc>
                        <chunk>
                            openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。
                        </chunk>
                        <chunk>
                            openEuler社区的目标是为用户提供一个稳定、安全、高效的操作系统平台，并且支持多种硬件架构。
                        </chunk>
                    </document>
                    <document id = 2 name = another_example_doc>
                        <chunk>
                            openEuler社区的成员来自世界各地，包括开发者、用户和企业。
                        </chunk>
                        <chunk>
                            openEuler社区的成员共同努力，推动开源操作系统的发展，并且为用户提供支持和帮助。
                        </chunk>
                    </document>
            </bac_info>
            <user_question>
                    openEuler社区的目标是什么？
            </user_question>
            <answer>
                    openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。[[1]]
                    openEuler社区的目标是为用户提供一个稳定、安全、高效的操作系统平台，并且支持多种硬件架构。[[1]]
            </answer>
        </example>
        
        <bac_info>
                {bac_info}
        </bac_info>
        <user_question>
                {user_question}
        </user_question>
        """,
        LanguageType.ENGLISH: r"""
        <instructions>
                You are a helpful assistant of openEuler community. Please answer the user's question based on the given background information and add footnotes after the related sentences.
                An example will be given in <example>.
                The background information will be given in <bac_info>.
                The user's question will be given in <user_question>.
                Note:
                1. Do not include any XML tags in the output, and do not make up any information. If you think the user's question is unrelated to the background information, please ignore the background information and directly answer.
                2. Your response should not exceed 250 words.
        </instructions>
        <example>
            <bac_info>
                    <document id = 1 name = example_doc>
                        <chunk>
                            openEuler community is an open source operating system community, committed to promoting the development of the Linux operating system.
                        </chunk>
                        <chunk>
                            openEuler community aims to provide users with a stable, secure, and efficient operating system platform, and support multiple hardware architectures.
                        </chunk>
                    </document>
                    <document id = 2 name = another_example_doc>        
                        <chunk>
                            Members of the openEuler community come from all over the world, including developers, users, and enterprises.
                        </chunk>
                        <chunk>
                            Members of the openEuler community work together to promote the development of open source operating systems, and provide support and assistance to users.
                        </chunk>
                    </document>
            </bac_info>
            <user_question>
                    What is the goal of openEuler community?
            </user_question>
            <answer>
                    openEuler community is an open source operating system community, committed to promoting the development of the Linux operating system. [[1]]
                    openEuler community aims to provide users with a stable, secure, and efficient operating system platform, and support multiple hardware architectures. [[1]]
            </answer>   
        </example>  

        <bac_info>
                {bac_info}
        </bac_info>
        <user_question>
                {user_question}
        </user_question>
        """,
    }

    @staticmethod
    async def get_doc_info_from_rag(
        user_sub: str, max_tokens: int, doc_ids: list[str], data: RAGQueryReq
    ) -> list[dict[str, Any]]:
        """获取RAG服务的文档信息"""
        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        url = Config().get_config().rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session_id}",
        }
        doc_chunk_list = []
        if doc_ids:
            default_kb_id = "00000000-0000-0000-0000-000000000000"
            tmp_data = RAGQueryReq(
                kbIds=[default_kb_id],
                query=data.query,
                topK=data.top_k,
                docIds=doc_ids,
                searchMethod=data.search_method,
                isRelatedSurrounding=data.is_related_surrounding,
                isClassifyByDoc=data.is_classify_by_doc,
                isRerank=data.is_rerank,
                tokensLimit=max_tokens,
            )
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    data_json = tmp_data.model_dump(exclude_none=True, by_alias=True)
                    response = await client.post(url, headers=headers, json=data_json)
                    if response.status_code == status.HTTP_200_OK:
                        result = response.json()
                        doc_chunk_list += result["result"]["docChunks"]
            except Exception as e:
                logger.error(f"[RAG] 获取文档分片失败: {e}")
        if data.kb_ids:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    data_json = data.model_dump(exclude_none=True, by_alias=True)
                    response = await client.post(url, headers=headers, json=data_json)
                    # 检查响应状态码
                    if response.status_code == status.HTTP_200_OK:
                        result = response.json()
                        doc_chunk_list += result["result"]["docChunks"]
            except Exception as e:
                logger.error(f"[RAG] 获取文档分片失败: {e}")
        return doc_chunk_list

    @staticmethod
    async def assemble_doc_info(doc_chunk_list: list[dict[str, Any]], max_tokens: int) -> str:
        """组装文档信息"""
        bac_info = ""
        doc_info_list = []
        doc_cnt = 0
        doc_id_map = {}
        leave_tokens = max_tokens
        token_calculator = TokenCalculator()
        for doc_chunk in doc_chunk_list:
            if doc_chunk["docId"] not in doc_id_map:
                doc_cnt += 1
                doc_id_map[doc_chunk["docId"]] = doc_cnt
            doc_index = doc_id_map[doc_chunk["docId"]]
            leave_tokens -= token_calculator.calculate_token_length(
                messages=[
                    {
                        "role": "user",
                        "content": f"""<document id="{doc_index}"  name="{doc_chunk["docName"]}">""",
                    },
                    {"role": "user", "content": "</document>"},
                ],
                pure_text=True,
            )
        tokens_of_chunk_element = token_calculator.calculate_token_length(
            messages=[
                {"role": "user", "content": "<chunk>"},
                {"role": "user", "content": "</chunk>"},
            ],
            pure_text=True,
        )
        doc_cnt = 0
        doc_id_map = {}
        for doc_chunk in doc_chunk_list:
            if doc_chunk["docId"] not in doc_id_map:
                doc_cnt += 1
                t = doc_chunk.get("docCreatedAt", None)
                if isinstance(t, str):
                    t = datetime.strptime(t, '%Y-%m-%d %H:%M')
                    t = round(t.replace(tzinfo=UTC).timestamp(), 3)
                else:
                    t = round(datetime.now(UTC).timestamp(), 3)
                doc_info_list.append({
                    "id": doc_chunk["docId"],
                    "order": doc_cnt,
                    "name": doc_chunk.get("docName", ""),
                    "author": doc_chunk.get("docAuthor", ""),
                    "extension": doc_chunk.get("docExtension", ""),
                    "abstract": doc_chunk.get("docAbstract", ""),
                    "size": doc_chunk.get("docSize", 0),
                    "created_at": t,
                })
                doc_id_map[doc_chunk["docId"]] = doc_cnt
            doc_index = doc_id_map[doc_chunk["docId"]]
            if bac_info:
                bac_info += "\n\n"
            bac_info += f'''
            <document id="{doc_index}"  name="{doc_chunk["docName"]}">
            '''
            for chunk in doc_chunk["chunks"]:
                if leave_tokens <= tokens_of_chunk_element:
                    break
                chunk_text = chunk["text"]
                chunk_text = TokenCalculator.get_k_tokens_words_from_content(
                    content=chunk_text, k=leave_tokens)
                leave_tokens -= token_calculator.calculate_token_length(messages=[
                    {"role": "user", "content": "<chunk>"},
                    {"role": "user", "content": chunk_text},
                    {"role": "user", "content": "</chunk>"},
                ], pure_text=True)
                bac_info += f'''
                <chunk>
                    {chunk_text}
                </chunk>
                '''
            bac_info += "</document>"
        return bac_info, doc_info_list

    @staticmethod
    async def chat_with_llm_base_on_rag(
        user_sub: str,
        llm: LLM,
        history: list[dict[str, str]],
        doc_ids: list[str],
        data: RAGQueryReq,
        language: LanguageType = LanguageType.CHINESE,
    ) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        reasion_llm = ReasoningLLM(
            LLMConfig(
                endpoint=llm.openai_base_url,
                key=llm.openai_api_key,
                model=llm.model_name,
                max_tokens=llm.max_tokens,
            )
        )
        if history:
            try:
                question_obj = QuestionRewrite()
                data.query = await question_obj.generate(
                    history=history, question=data.query, llm=reasion_llm, language=language
                )
            except Exception:
                logger.exception("[RAG] 问题重写失败")
        doc_chunk_list = await RAG.get_doc_info_from_rag(
            user_sub=user_sub, max_tokens=llm.max_tokens, doc_ids=doc_ids, data=data)
        bac_info, doc_info_list = await RAG.assemble_doc_info(
            doc_chunk_list=doc_chunk_list, max_tokens=llm.max_tokens)
        messages = [
            *history,
            {
                "role": "system",
                "content": RAG.system_prompt,
            },
            {
                "role": "user",
                "content": RAG.user_prompt[language].format(
                    bac_info=bac_info,
                    user_question=data.query,
                ),
            },
        ]
        input_tokens = TokenCalculator().calculate_token_length(messages=messages)
        output_tokens = 0
        doc_cnt = 0
        for doc_info in doc_info_list:
            doc_cnt = max(doc_cnt, doc_info["order"])
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.DOCUMENT_ADD.value,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "content": doc_info,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
        max_footnote_length = 4
        tmp_doc_cnt = doc_cnt
        while tmp_doc_cnt > 0:
            tmp_doc_cnt //= 10
            max_footnote_length += 1
        buffer = ""
        async for chunk in reasion_llm.call(
            messages,
            max_tokens=llm.max_tokens,
            streaming=True,
            temperature=0.7,
            result_only=False,
            model=llm.model_name,
        ):
            chunk = buffer + chunk
            # 防止脚注被截断
            if len(chunk) >= 2 and chunk[-2:] != "]]":
                index = len(chunk) - 1
                while index >= max(0, len(chunk) - max_footnote_length) and chunk[index] != "]":
                    index -= 1
                if index >= 0:
                    buffer = chunk[index + 1:]
                    chunk = chunk[:index + 1]
            else:
                buffer = ""
            # 匹配脚注
            footnotes = re.findall(r"\[\[\d+\]\]", chunk)
            # 去除编号大于doc_cnt的脚注
            footnotes = [fn for fn in footnotes if int(fn[2:-2]) > doc_cnt]
            footnotes = list(set(footnotes))  # 去重
            if footnotes:
                for fn in footnotes:
                    chunk = chunk.replace(fn, "")
            output_tokens += TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "assistant", "content": chunk},
                ],
                pure_text=True,
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.TEXT_ADD.value,
                        "content": chunk,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
        if buffer:
            output_tokens += TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "assistant", "content": buffer},
                ],
                pure_text=True,
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.TEXT_ADD.value,
                        "content": buffer,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
