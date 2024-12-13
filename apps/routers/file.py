# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import time
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from starlette.responses import JSONResponse
import aiofiles
import uuid

from apps.common.config import config
from apps.scheduler.files import Files
from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import verify_user

router = APIRouter(
    prefix="/api/file",
    tags=["file"],
    dependencies=[
        Depends(verify_csrf_token),
        Depends(verify_user),
    ]
)


@router.post("")
async def data_report_upload(files: List[UploadFile] = File(...)):
    file_ids = []

    for file in files:
        file_id = str(uuid.uuid4())
        file_ids.append(file_id)

        current_filename = file.filename
        suffix = current_filename.split(".")[-1]

        async with aiofiles.open("{}/{}.{}".format(config["TEMP_DIR"], file_id, suffix), 'wb') as f:
            content = await file.read()
            await f.write(content)

        file_metadata = {
            "time": time.time(),
            "name": current_filename,
            "path": "{}/{}.{}".format(config["TEMP_DIR"], file_id, suffix)
        }

        Files.add(file_id, file_metadata)

    return JSONResponse(status_code=200, content={
        "files": file_ids,
    })
