# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from fastapi import APIRouter, Depends, status

from apps.dependency.user import get_user, verify_user
from apps.dependency.csrf import verify_csrf_token
from apps.entities.response_data import ResponseData
from apps.entities.user import User
from apps.manager.api_key import ApiKeyManager

router = APIRouter(
    prefix="/api/auth/key",
    tags=["key"],
    dependencies=[Depends(verify_user)]
)


@router.get("", response_model=ResponseData)
def check_api_key_existence(user: User = Depends(get_user)):
    exists: bool = ApiKeyManager.api_key_exists(user)
    return ResponseData(code=status.HTTP_200_OK, message="success", result={
        "api_key_exists": exists
    })


@router.post("", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
def manage_api_key(action: str, user: User = Depends(get_user)):
    action = action.lower()
    if action == "create":
        api_key: str = ApiKeyManager.generate_api_key(user)
    elif action == "update":
        api_key: str = ApiKeyManager.update_api_key(user)
    elif action == "delete":
        success = ApiKeyManager.delete_api_key(user)
        if success:
            return ResponseData(code=status.HTTP_200_OK, message="success", result={})
        return ResponseData(code=status.HTTP_400_BAD_REQUEST, message="failed to revoke api key", result={})
    else:
        return ResponseData(code=status.HTTP_400_BAD_REQUEST, message="invalid request body", result={})
    if api_key is None:
        return ResponseData(code=status.HTTP_400_BAD_REQUEST, message="failed to generate api key", result={})
    return ResponseData(code=status.HTTP_200_OK, message="success", result={
        "api_key": api_key
    })
