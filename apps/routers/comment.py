# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 评论相关接口"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.comment import AddCommentData
from apps.schemas.record import RecordComment
from apps.schemas.response_data import ResponseData
from apps.services.comment import CommentManager

_logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/comment",
    tags=["comment"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.post("", response_model=ResponseData)
async def add_comment(request: Request, post_body: AddCommentData) -> JSONResponse:
    """POST /comment: 给Record添加评论"""
    comment_data = RecordComment(
        comment=post_body.comment,
        dislike_reason=post_body.dislike_reason.split(";")[:-1],
        reason_link=post_body.reason_link,
        reason_description=post_body.reason_description,
        feedback_time=round(datetime.now(tz=UTC).timestamp(), 3),
    )
    result = await CommentManager.update_comment(post_body.record_id, comment_data, request.state.user_id)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(
                ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="record_id not found",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            ResponseData(
                code=status.HTTP_200_OK,
                message="success",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        ),
    )
