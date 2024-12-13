# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    user_sub: str = Field(..., description="user sub")
    revision_number: Optional[str] = None
