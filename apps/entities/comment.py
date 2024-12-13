# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from dataclasses import dataclass


@dataclass
class CommentData:
    record_id: str
    is_like: bool
    dislike_reason: str
    reason_link: str
    reason_description: str
