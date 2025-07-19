# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""代码执行工具"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from pydantic import Field

from apps.common.config import Config
from apps.scheduler.call.code.schema import CodeInput, CodeOutput
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class Code(CoreCall, input_model=CodeInput, output_model=CodeOutput):
    """代码执行工具"""

    to_user: bool = Field(default=True)

    # 代码执行参数
    code: str = Field(description="要执行的代码", default="")
    code_type: str = Field(description="代码类型，支持python、javascript、bash", default="python")
    security_level: str = Field(description="安全等级，low或high", default="low")
    timeout_seconds: int = Field(description="超时时间（秒）", default=30, ge=1, le=300)
    memory_limit_mb: int = Field(description="内存限制（MB）", default=128, ge=1, le=1024)
    cpu_limit: float = Field(description="CPU限制", default=0.5, ge=0.1, le=2.0)


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="代码执行", description="在安全的沙箱环境中执行Python、JavaScript、Bash代码。")


    async def _init(self, call_vars: CallVars) -> CodeInput:
        """初始化代码执行工具"""
        # 构造用户信息
        user_info = {
            "user_id": call_vars.ids.user_sub,
            "username": call_vars.ids.user_sub,  # 可以从其他地方获取真实用户名
            "permissions": ["execute"]
        }

        return CodeInput(
            code=self.code,
            code_type=self.code_type,
            user_info=user_info,
            security_level=self.security_level,
            timeout_seconds=self.timeout_seconds,
            memory_limit_mb=self.memory_limit_mb,
            cpu_limit=self.cpu_limit,
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行代码"""
        data = CodeInput(**input_data)
        
        try:
            # 获取sandbox服务地址
            config = Config().get_config()
            sandbox_url = config.sandbox.sandbox_service
            
            # 构造请求数据
            request_data = {
                "code": data.code,
                "code_type": data.code_type,
                "user_info": data.user_info,
                "security_level": data.security_level,
                "timeout_seconds": data.timeout_seconds,
                "memory_limit_mb": data.memory_limit_mb,
                "cpu_limit": data.cpu_limit,
            }
            
            # 发送执行请求
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{sandbox_url.rstrip('/')}/execute",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise CallError(
                        message=f"代码执行服务请求失败: {response.status_code}",
                        data={"status_code": response.status_code, "response": response.text}
                    )
                
                result = response.json()
                task_id = result.get("task_id", "")
                
                # 轮询获取结果
                if task_id:
                    result = await self._wait_for_result(sandbox_url, task_id)
                
                # 返回结果
                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=CodeOutput(
                        task_id=task_id,
                        status=result.get("status", "unknown"),
                        result=result.get("result", {}),
                        output=result.get("output", ""),
                        error=result.get("error", ""),
                    ).model_dump(by_alias=True, exclude_none=True),
                )
                
        except httpx.TimeoutException:
            raise CallError(message="代码执行超时", data={})
        except httpx.RequestError as e:
            raise CallError(message=f"请求sandbox服务失败: {e!s}", data={})
        except Exception as e:
            raise CallError(message=f"代码执行失败: {e!s}", data={})


    async def _wait_for_result(self, sandbox_url: str, task_id: str, max_attempts: int = 30) -> dict[str, Any]:
        """等待任务执行完成"""
        import asyncio
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(max_attempts):
                try:
                    # 获取任务状态
                    response = await client.get(f"{sandbox_url.rstrip('/')}/task/{task_id}/status")
                    if response.status_code == 200:
                        status_result = response.json()
                        status = status_result.get("status", "")
                        
                        # 如果任务完成，获取结果
                        if status in ["completed", "failed", "cancelled"]:
                            result_response = await client.get(f"{sandbox_url.rstrip('/')}/task/{task_id}/result")
                            if result_response.status_code == 200:
                                return result_response.json()
                            else:
                                return {"status": status, "error": "无法获取结果"}
                        
                        # 如果任务仍在运行，继续等待
                        if status in ["pending", "running"]:
                            await asyncio.sleep(1)
                            continue
                    
                    # 其他状态或请求失败，等待后重试
                    await asyncio.sleep(1)
                    
                except Exception:
                    # 请求异常，等待后重试
                    await asyncio.sleep(1)
            
            # 超时返回
            return {"status": "timeout", "error": "等待任务完成超时"} 