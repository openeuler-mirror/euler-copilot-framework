"""FastAPI 评论相关接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.constants import LOGGER
from apps.dependency import get_user, verify_csrf_token, verify_user
from apps.entities.collection import RecordComment
from apps.entities.request_data import AddCommentData
from apps.entities.response_data import ResponseData
from apps.manager.comment import CommentManager
from apps.manager.record import RecordManager

router = APIRouter(
    prefix="/api/comment",
    tags=["comment"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.post("", dependencies=[Depends(verify_csrf_token)], response_model=ResponseData)
async def add_comment(post_body: AddCommentData, user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """给Record添加评论"""
    if not await RecordManager.verify_record_in_group(post_body.group_id, post_body.record_id, user_sub):
        LOGGER.error("Comment: record_id not found.")
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=ResponseData(
            code=status.HTTP_204_NO_CONTENT,
            message="record_id not found",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    comment_data = RecordComment(
        is_liked=post_body.is_like,
        feedback_type=post_body.dislike_reason,
        feedback_link=post_body.reason_link,
        feedback_content=post_body.reason_description,
        feedback_time=round(datetime.now(tz=timezone.utc).timestamp(), 3),
    )
    await CommentManager.update_comment(post_body.group_id, post_body.record_id, comment_data)
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="success",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
