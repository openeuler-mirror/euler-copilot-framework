# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""代码沙箱相关接口"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
import httpx

from apps.common.config import Config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/sandbox",
    tags=["sandbox"],
)

def get_sandbox_service_url() -> str:
    """从配置中获取沙箱服务地址"""
    config = Config().get_config()
    return config.sandbox.sandbox_service


@router.get("/code-spec/{language}")
async def get_code_specification(
    language: str = Path(..., description="编程语言类型: python, javascript, bash, shell"),
    lang: str = "zh"
) -> JSONResponse:
    """
    获取指定编程语言的代码安全规范文档
    
    Args:
        language: 编程语言类型，可选值: python, javascript, bash, shell
        lang: 文档语言，可选值: zh(中文), en(英文)，默认为 zh
    
    Returns:
        对应语言的安全规范文档内容（Markdown格式）
    """
    try:
        # 标准化语言参数
        language_lower = language.lower()
        if language_lower not in ['python', 'javascript', 'bash', 'shell']:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的语言类型: {language}。支持的类型: python, javascript, bash, shell"
            )
        
        # 标准化文档语言参数
        doc_lang = lang.lower() if lang.lower() in ['zh', 'en'] else 'zh'
        
        # 获取沙箱服务地址
        sandbox_url = get_sandbox_service_url()
        
        # 转发请求到沙箱服务，带上语言参数
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{sandbox_url}/code-spec/{language_lower}",
                params={"lang": doc_lang}
            )
            
            if response.status_code != 200:
                logger.error(f"沙箱服务返回错误: {response.status_code}, {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="获取代码规范失败"
                )
            
            result = response.json()
            
            # 返回标准格式
            return JSONResponse(
                status_code=200,
                content={
                    "success": result.get("success", True),
                    "message": result.get("message", "获取代码规范成功"),
                    "data": result.get("data", {})
                }
            )
            
    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("请求沙箱服务超时")
        raise HTTPException(
            status_code=504,
            detail="请求代码沙箱服务超时，请稍后重试"
        )
    except httpx.RequestError as e:
        logger.error(f"请求沙箱服务失败: {e}")
        raise HTTPException(
            status_code=503,
            detail="无法连接到代码沙箱服务"
        )
    except Exception as e:
        logger.error(f"获取代码规范失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"获取代码规范失败: {str(e)}"
        )


@router.get("/health")
async def sandbox_health_check() -> JSONResponse:
    """
    检查代码沙箱服务健康状态
    
    Returns:
        沙箱服务健康状态
    """
    try:
        # 获取沙箱服务地址
        sandbox_url = get_sandbox_service_url()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{sandbox_url}/health")
            
            if response.status_code == 200:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "沙箱服务运行正常",
                        "data": response.json().get("data", {})
                    }
                )
            else:
                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "message": "沙箱服务不可用",
                        "data": None
                    }
                )
    except Exception as e:
        logger.error(f"检查沙箱服务健康状态失败: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "无法连接到沙箱服务",
                "data": None
            }
        )

