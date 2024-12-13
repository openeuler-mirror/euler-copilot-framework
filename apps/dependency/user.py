# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.entities.user import User
from apps.manager.api_key import ApiKeyManager
from apps.manager.session import SessionManager

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_user(request: HTTPConnection):
    """
    验证Session是否已鉴权；未鉴权则抛出HTTP 401
    接口级dependence
    :param request: HTTP请求
    :return:
    """
    session_id = request.cookies["ECSESSION"]
    if not SessionManager.verify_user(session_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication Error.")

def get_session(request: HTTPConnection):
    """
    验证Session是否已鉴权，并返回Session ID；未鉴权则抛出HTTP 401
    参数级dependence
    :param request: HTTP请求
    :return: Session ID
    """
    session_id = request.cookies["ECSESSION"]
    if not SessionManager.verify_user(session_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication Error.")
    return session_id

def get_user(request: HTTPConnection) -> User:
    """
    验证Session是否已鉴权；若已鉴权，查询对应的user_sub；若未鉴权，抛出HTTP 401
    参数级dependence
    :param request:
    :return:
    """
    session_id = request.cookies["ECSESSION"]
    user = SessionManager.get_user(session_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication Error.")
    return user


def verify_api_key(api_key: str = Depends(oauth2_scheme)):
    if not ApiKeyManager.verify_api_key(api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key!")


def get_user_by_api_key(api_key: str = Depends(oauth2_scheme)) -> User:
    user = ApiKeyManager.get_user_by_api_key(api_key)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key!")
    return user
