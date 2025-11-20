# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于执行智能问答的Executor"""

import logging
import uuid
from datetime import UTC, datetime

from apps.models import ExecutorCheckpoint, ExecutorStatus, StepStatus, StepType
from apps.models.task import LanguageType
from apps.scheduler.call.rag.schema import DocItem, RAGOutput
from apps.schemas.document import DocumentInfo
from apps.schemas.enum_var import SpecialCallType
from apps.schemas.flow import Step
from apps.schemas.task import StepQueueItem

from .base import BaseExecutor
from .step import StepExecutor

_logger = logging.getLogger(__name__)
_RAG_STEP_LIST = [
    {
        LanguageType.CHINESE: Step(
            name="RAG检索",
            description="从知识库中检索相关文档",
            node="RAG",
            type=StepType.RAG.value,
        ),
        LanguageType.ENGLISH: Step(
            name="RAG retrieval",
            description="Retrieve relevant documents from the knowledge base",
            node="RAG",
            type=StepType.RAG.value,
        ),
    },
    {
        LanguageType.CHINESE: Step(
            name="LLM问答",
            description="基于检索到的文档生成答案",
            node="LLM",
            type=StepType.LLM.value,
        ),
        LanguageType.ENGLISH: Step(
            name="LLM answer",
            description="Generate answer based on the retrieved documents",
            node="LLM",
            type=StepType.LLM.value,
        ),
    },
    {
        LanguageType.CHINESE: Step(
            name="问题推荐",
            description="根据对话答案，推荐相关问题",
            node="Suggestion",
            type=StepType.SUGGEST.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Question Suggestion",
            description="Display the suggested next question under the answer",
            node="Suggestion",
            type=StepType.SUGGEST.value,
        ),
    },
    {
        LanguageType.CHINESE: Step(
            name="记忆存储",
            description="理解对话答案，并存储到记忆中",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Memory storage",
            description="Understand the answer of the dialogue and store it in the memory",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
    },
]


class QAExecutor(BaseExecutor):
    """用于执行智能问答的Executor"""

    async def init(self) -> None:
        """初始化QAExecutor"""
        await self._load_history()
        self.task.state = ExecutorCheckpoint(
            taskId=self.task.metadata.id,
            executorId="QAExecutor",
            executorName="QAExecutor",
            executorStatus=ExecutorStatus.RUNNING,
            stepStatus=StepStatus.RUNNING,
            stepId=uuid.uuid4(),
            stepName="QAExecutor",
            stepType="",
            appId=None,
        )

    async def _assemble_doc_info(
        self,
        doc_chunk_list: list[DocItem],
        max_tokens: int,
    ) -> list[DocumentInfo]:
        """组装文档信息"""
        doc_info_list = []
        doc_cnt = 0
        doc_id_map = {}
        _ = round(max_tokens * 0.8)

        for doc_chunk in doc_chunk_list:
            if doc_chunk.docId not in doc_id_map:
                doc_cnt += 1
                created_at_value = (
                    doc_chunk.docCreatedAt.timestamp()
                    if isinstance(doc_chunk.docCreatedAt, datetime)
                    else doc_chunk.docCreatedAt
                )
                doc_info = DocumentInfo(
                    id=doc_chunk.docId,
                    order=doc_cnt,
                    name=doc_chunk.docName,
                    author=doc_chunk.docAuthor,
                    extension=doc_chunk.docExtension,
                    abstract=doc_chunk.docAbstract,
                    size=doc_chunk.docSize,
                    created_at=created_at_value,
                )
                doc_info_list.append(doc_info)
                doc_id_map[doc_chunk.docId] = doc_cnt

        return doc_info_list

    async def _execute_rag_step(self) -> bool:
        """执行RAG检索步骤"""
        _logger.info("[QAExecutor] 开始执行RAG检索步骤")

        rag_exec = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=StepQueueItem(
                step_id=uuid.uuid4(),
                step=_RAG_STEP_LIST[0][self.task.runtime.language],
                enable_filling=False,
                to_user=False,
            ),
            background=self.background,
            question=self.question,
            llm=self.llm,
        )
        await rag_exec.init()
        await rag_exec.run()

        if self.task.state and self.task.state.stepStatus == StepStatus.ERROR:
            _logger.error("[QAExecutor] RAG检索步骤失败")
            self.task.state.executorStatus = ExecutorStatus.ERROR
            return False

        rag_output_data = None
        for history in self.task.context:
            if history.stepId == rag_exec.step.step_id:
                rag_output_data = history.outputData
                break

        if rag_output_data and isinstance(rag_output_data, dict):
            rag_output = RAGOutput.model_validate(rag_output_data)
            doc_chunk_list: list[DocItem] = [
                DocItem.model_validate(item) if not isinstance(item, DocItem) else item
                for item in rag_output.corpus
            ]
            doc_info_list = await self._assemble_doc_info(doc_chunk_list, 8192)
            for doc_info in doc_info_list:
                await self._push_message(
                    "document.add",
                    doc_info.model_dump(by_alias=True, exclude_none=True),
                )
            _logger.info("[QAExecutor] RAG检索步骤成功，已推送%d个文档", len(doc_info_list))
        else:
            _logger.warning("[QAExecutor] RAG检索步骤未返回有效数据")

        return True

    async def _execute_llm_step(self) -> bool:
        """执行LLM问答步骤"""
        _logger.info("[QAExecutor] 开始执行LLM问答步骤")

        llm_exec = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=StepQueueItem(
                step_id=uuid.uuid4(),
                step=_RAG_STEP_LIST[1][self.task.runtime.language],
                enable_filling=False,
                to_user=True,
            ),
            background=self.background,
            question=self.question,
            llm=self.llm,
        )
        await llm_exec.init()
        await llm_exec.run()

        if self.task.state and self.task.state.stepStatus == StepStatus.ERROR:
            _logger.error("[QAExecutor] LLM问答步骤失败")
            self.task.state.executorStatus = ExecutorStatus.ERROR
            return False

        _logger.info("[QAExecutor] LLM问答步骤完成")
        return True

    async def _execute_remaining_steps(self) -> bool:
        """执行剩余步骤：问题推荐和记忆存储"""
        _logger.info("[QAExecutor] 开始执行问题推荐步骤")
        suggestion_exec = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=StepQueueItem(
                step_id=uuid.uuid4(),
                step=_RAG_STEP_LIST[2][self.task.runtime.language],
                enable_filling=False,
                to_user=True,
            ),
            background=self.background,
            question=self.question,
            llm=self.llm,
        )
        await suggestion_exec.init()
        await suggestion_exec.run()

        if self.task.state and self.task.state.stepStatus == StepStatus.ERROR:
            _logger.error("[QAExecutor] 问题推荐步骤失败")
            self.task.state.executorStatus = ExecutorStatus.ERROR
            return False

        _logger.info("[QAExecutor] 开始执行记忆存储步骤")
        facts_exec = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=StepQueueItem(
                step_id=uuid.uuid4(),
                step=_RAG_STEP_LIST[3][self.task.runtime.language],
                enable_filling=False,
                to_user=False,
            ),
            background=self.background,
            question=self.question,
            llm=self.llm,
        )
        await facts_exec.init()
        await facts_exec.run()

        if self.task.state and self.task.state.stepStatus == StepStatus.ERROR:
            _logger.error("[QAExecutor] 记忆存储步骤失败")
            self.task.state.executorStatus = ExecutorStatus.ERROR
            return False

        return True

    async def run(self) -> None:
        """运行QA"""
        _logger.info("[QAExecutor] 开始运行QA流程")

        if not self.task.state:
            error = Exception("[QAExecutor] task.state不存在，无法执行")
            raise error

        rag_success = await self._execute_rag_step()
        if not rag_success:
            _logger.error("[QAExecutor] RAG检索步骤失败，终止执行")
            return

        llm_success = await self._execute_llm_step()
        if not llm_success:
            _logger.error("[QAExecutor] LLM问答步骤失败，终止执行")
            return

        remaining_success = await self._execute_remaining_steps()
        if not remaining_success:
            _logger.error("[QAExecutor] 剩余步骤失败，终止执行")
            return

        self.task.runtime.fullTime = round(datetime.now(UTC).timestamp(), 2) - self.task.runtime.time
        self.task.state.executorStatus = ExecutorStatus.SUCCESS

        _logger.info("[QAExecutor] QA流程完成")
