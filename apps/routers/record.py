"""FastAPI Record相关接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.common.security import Security
from apps.dependency import get_user, verify_user
from apps.entities.collection import (
    RecordContent,
)
from apps.entities.record import RecordData, RecordFlow, RecordFlowStep, RecordMetadata
from apps.entities.response_data import (
    RecordListMsg,
    RecordListRsp,
    ResponseData,
)
from apps.manager.conversation import ConversationManager
from apps.manager.document import DocumentManager
from apps.manager.record import RecordManager
from apps.manager.task import TaskManager

router = APIRouter(
    prefix="/api/record",
    tags=["record"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get("/{conversation_id}", response_model=RecordListRsp, responses={status.HTTP_403_FORBIDDEN: {"model": ResponseData}})
async def get_record(conversation_id: str, user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """获取某个对话的所有问答对"""
    cur_conv = await ConversationManager.get_conversation_by_conversation_id(user_sub, conversation_id)
    # 判断conversation是否合法
    if not cur_conv:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="Conversation invalid.",
                result={},
            ).model_dump(exclude_none=True),
        )

    record_group_list = await RecordManager.query_record_group_by_conversation_id(conversation_id)
    result = []
    for record_group in record_group_list:
        for record in record_group.records:
            record_data = Security.decrypt(record.data, record.key)
            record_data = RecordContent.model_validate(json.loads(record_data))

            tmp_record = RecordData(
                id=record.record_id,
                groupId=record_group.id,
                taskId=record_group.task_id,
                conversationId=conversation_id,
                content=record_data,
                metadata=record.metadata if record.metadata else RecordMetadata(
                    input_tokens=0,
                    output_tokens=0,
                    time_cost=0,
                ),
                createdAt=record.created_at,
            )

            # 获得Record关联的文档
            tmp_record.document = await DocumentManager.get_used_docs_by_record_group(user_sub, record_group.id)

            # 获得Record关联的flow数据
            flow_list = await TaskManager.get_flow_history_by_record_id(record_group.id, record.record_id)
            if flow_list:
                tmp_record.flow = RecordFlow(
                    id=flow_list[0].id,
                    recordId=record.record_id,
                    flowId=flow_list[0].flow_id,
                    stepNum=len(flow_list),
                    steps=[],
                )
                for flow in flow_list:
                    tmp_record.flow.steps.append(RecordFlowStep(
                        stepId=flow.step_id,
                        stepStatus=flow.status,
                        input=flow.input_data ,
                        output=flow.output_data,
                    ))

            result.append(tmp_record)
    return JSONResponse(status_code=status.HTTP_200_OK,
        content=RecordListRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=RecordListMsg(records=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )
