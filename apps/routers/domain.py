# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from fastapi import APIRouter, Depends, HTTPException, status

from apps.entities.request_data import AddDomainData
from apps.entities.response_data import ResponseData
from apps.manager.domain import DomainManager
from apps.dependency.csrf import verify_csrf_token
from apps.dependency.user import verify_user


router = APIRouter(
    prefix='/api/domain',
    tags=['domain'],
    dependencies=[
        Depends(verify_csrf_token),
        Depends(verify_user),
    ]
)


@router.post('', response_model=ResponseData)
async def add_domain(post_body: AddDomainData):
    if DomainManager.get_domain_by_domain_name(post_body.domain_name):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="add domain name is exist.")
    if not DomainManager.add_domain(post_body):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="add domain failed")
    return ResponseData(code=status.HTTP_200_OK, message="add domain success.", result={})


@router.put('')
async def update_domain(post_body: AddDomainData):
    if not DomainManager.get_domain_by_domain_name(post_body.domain_name):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="update domain name is not exist.")
    if not DomainManager.update_domain_by_domain_name(post_body):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="update domain failed")
    return ResponseData(code=status.HTTP_200_OK, message="update domain success.", result={})


@router.post("/delete", response_model=ResponseData)
async def delete_domain(post_body: AddDomainData):
    if not DomainManager.get_domain_by_domain_name(post_body.domain_name):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="delete domain name is not exist.")
    if not DomainManager.delete_domain_by_domain_name(post_body):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="delete domain failed")
    return ResponseData(code=status.HTTP_200_OK, message="delete domain success.", result={})
