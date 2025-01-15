"""生成FastAPI OpenAPI文档

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""  # noqa: INP001
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.openapi.utils import get_openapi

from apps.main import app


def get_api_doc() -> None:
    """获取API文档"""
    config_path = os.getenv("CONFIG")
    if not config_path:
        err = "CONFIG is not set"
        raise ValueError(err)

    path = Path(config_path) / "openapi.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        ), f, ensure_ascii=False)


if __name__ == "__main__":
    get_api_doc()
