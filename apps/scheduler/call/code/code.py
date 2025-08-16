# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""代码执行工具"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

import httpx
from pydantic import Field

from apps.common.config import Config
from apps.scheduler.call.code.schema import CodeInput, CodeOutput
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
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
    controlled_output: bool = Field(default=True)

    # 代码执行参数
    code: str = Field(description="要执行的代码", default="")
    code_type: str = Field(description="代码类型，支持python、javascript、bash", default="python")
    security_level: str = Field(description="安全等级，low或high", default="low")
    timeout_seconds: int = Field(description="超时时间（秒）", default=30, ge=1, le=300)
    memory_limit_mb: int = Field(description="内存限制（MB）", default=128, ge=1, le=1024)
    cpu_limit: float = Field(description="CPU限制", default=0.5, ge=0.1, le=2.0)
    input_parameters: dict[str, Any] = Field(description="输入参数配置", default={})
    output_parameters: dict[str, Any] = Field(description="输出参数配置", default={})
    
    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "代码执行",
            "type": CallType.TOOL,
            "description": "在安全的沙箱环境中执行Python、JavaScript、Bash代码",
        },
        LanguageType.ENGLISH: {
            "name": "Code",
            "type": CallType.TOOL,
            "description": "Executing Python, JavaScript, Bash in secure sandbox",
        },
    }

    async def _init(self, call_vars: CallVars) -> CodeInput:
        """初始化代码执行工具"""
        # 构造用户信息
        user_info = {
            "user_id": call_vars.ids.user_sub,
            "username": call_vars.ids.user_sub,  # 可以从其他地方获取真实用户名
            "permissions": ["execute"]
        }

        # 处理输入参数 - 直接从input_parameters读取
        input_arg = {}
        
        logger.info(f"[Code] 开始处理输入参数")
        logger.info(f"[Code] self.input_parameters: {self.input_parameters}")
        logger.info(f"[Code] self.output_parameters: {self.output_parameters}")
        
        if self.input_parameters:
            logger.info(f"[Code] 开始解析 {len(self.input_parameters)} 个输入参数")
            # 解析每个输入参数
            for param_name, param_config in self.input_parameters.items():
                logger.info(f"[Code] 正在解析参数: {param_name}, 配置: {param_config}")
                try:
                    resolved_value = await self._resolve_variables_in_config(param_config, call_vars)
                    input_arg[param_name] = resolved_value
                    logger.info(f"[Code] 参数 {param_name} 解析成功: {resolved_value}")
                except Exception as e:
                    logger.error(f"[Code] 参数 {param_name} 解析失败: {e}")
                    # 使用原始配置作为降级
                    input_arg[param_name] = param_config
        else:
            logger.warning("[Code] input_parameters 为空或未配置")

        logger.info(f"[Code] 最终的 input_arg: {input_arg}")

        return CodeInput(
            code=self.code,
            code_type=self.code_type,
            user_info=user_info,
            security_level=self.security_level,
            timeout_seconds=self.timeout_seconds,
            memory_limit_mb=self.memory_limit_mb,
            cpu_limit=self.cpu_limit,
            input_arg=input_arg,
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
                "input_arg": data.input_arg,
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
                logger.info(f"Sandbox service response: {result}")
                
                # 检查请求是否成功
                success = result.get("success", False)
                message = result.get("message", "")
                timestamp = result.get("timestamp", "")
                
                if not success:
                    raise CallError(
                        message=f"代码执行服务返回错误: {message}",
                        data={"response": result}
                    )
                
                # 提取任务信息
                data = result.get("data", {})
                task_id = data.get("task_id", "")
                estimated_wait_time = data.get("estimated_wait_time", 0)
                queue_position = data.get("queue_position", 0)
                
                logger.info(f"Task submitted successfully - task_id: {task_id}, estimated_wait_time: {estimated_wait_time}s, queue_position: {queue_position}, timestamp: {timestamp}")
                
                # 轮询获取结果
                if task_id:
                    # 有task_id，需要轮询获取最终结果
                    result = await self._wait_for_result(sandbox_url, task_id)
                else:
                    # 没有task_id，可能是同步执行，直接使用初始响应
                    # 但需要确保结果格式正确
                    if "output" not in result and "error" not in result:
                        # 如果初始响应没有包含执行结果，可能是异步但没有返回task_id的错误情况
                        result = {
                            "status": "error",
                            "error": "服务器没有返回task_id且没有执行结果",
                            "output": "",
                            "result": {}
                        }
                
                # 处理sandbox返回的结果，提取output_parameters指定的数据
                extracted_data = await self._process_sandbox_result(result)
                
                # 构建最终输出内容
                final_content = CodeOutput(
                    task_id=task_id,
                    status=result.get("status", "unknown"),
                    output=result.get("output") or "",
                    error=result.get("error") or "",
                ).model_dump(by_alias=True, exclude_none=True)
                
                # 如果成功提取到数据，将其合并到输出中
                if extracted_data and result.get("status") == "completed":
                    final_content.update(extracted_data)
                    logger.info(f"[Code] 已将提取的数据合并到输出: {list(extracted_data.keys())}")
                
                # 返回最终结果
                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=final_content,
                )
                
        except httpx.TimeoutException:
            raise CallError(message="代码执行超时", data={})
        except httpx.RequestError as e:
            raise CallError(message=f"请求sandbox服务失败: {e!s}", data={})
        except Exception as e:
            raise CallError(message=f"代码执行失败: {e!s}", data={})


    async def _process_sandbox_result(self, result: dict[str, Any]) -> dict[str, Any] | None:
        """处理sandbox返回的结果，根据output_parameters提取数据"""
        try:
            # 检查是否有output_parameters配置
            if not hasattr(self, 'output_parameters') or not self.output_parameters:
                logger.debug("[Code] 无output_parameters配置，跳过数据提取")
                return None
            
            # 获取sandbox返回的output
            sandbox_output = result.get("output")
            if not sandbox_output:
                logger.warning("[Code] sandbox返回的结果中没有output字段")
                return None
            
            # 确保output是字典类型
            if isinstance(sandbox_output, str):
                # 尝试解析JSON字符串
                try:
                    import json
                    sandbox_output = json.loads(sandbox_output)
                except json.JSONDecodeError:
                    logger.warning(f"[Code] sandbox返回的output不是有效的JSON格式: {sandbox_output}")
                    return None
            
            if not isinstance(sandbox_output, dict):
                logger.warning(f"[Code] sandbox返回的output不是字典类型: {type(sandbox_output)}")
                return None
            
            # 根据output_parameters提取对应的kv对
            extracted_data = {}
            for param_name, param_config in self.output_parameters.items():
                try:
                    # 支持多种提取方式
                    if param_name in sandbox_output:
                        # 直接键匹配
                        extracted_data[param_name] = sandbox_output[param_name]
                    elif isinstance(param_config, dict) and "path" in param_config:
                        # 路径提取
                        path = param_config["path"]
                        value = self._extract_value_by_path(sandbox_output, path)
                        if value is not None:
                            extracted_data[param_name] = value
                    elif isinstance(param_config, dict) and param_config.get("source") == "full_output":
                        # 使用完整输出
                        extracted_data[param_name] = sandbox_output
                    elif isinstance(param_config, dict) and "default" in param_config:
                        # 使用默认值
                        extracted_data[param_name] = param_config["default"]
                    else:
                        logger.debug(f"[Code] 无法提取参数 {param_name}，在output中未找到对应值")
                        
                except Exception as e:
                    logger.warning(f"[Code] 提取参数 {param_name} 失败: {e}")
            
            if extracted_data:
                logger.info(f"[Code] 成功提取 {len(extracted_data)} 个输出参数: {list(extracted_data.keys())}")
                return extracted_data
            else:
                logger.debug("[Code] 未能提取到任何输出参数")
                return None
                
        except Exception as e:
            logger.error(f"[Code] 处理sandbox结果失败: {e}")
            return None
    
    def _extract_value_by_path(self, data: dict, path: str) -> Any:
        """根据路径提取值 (例如: 'result.data.value')"""
        try:
            current = data
            for key in path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            return current
        except Exception:
            return None


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
                        logger.info(f"Task status response: {status_result}")
                        
                        # 检查响应是否成功
                        success = status_result.get("success", False)
                        if not success:
                            message = status_result.get("message", "获取任务状态失败")
                            logger.warning(f"Failed to get task status: {message}")
                            await asyncio.sleep(1)
                            continue
                        
                        # 提取任务状态
                        data = status_result.get("data", {})
                        status = data.get("status", "")
                        
                        # 如果任务完成，获取结果
                        if status in ["completed", "failed", "cancelled"]:
                            result_response = await client.get(f"{sandbox_url.rstrip('/')}/task/{task_id}/result")
                            if result_response.status_code == 200:
                                result_data = result_response.json()
                                logger.info(f"Task result response: {result_data}")
                                
                                # 检查获取结果是否成功
                                if result_data.get("success", False):
                                    # 返回实际的执行结果
                                    return result_data.get("data", {})
                                else:
                                    return {"status": status, "error": result_data.get("message", "获取结果失败")}
                            else:
                                return {"status": status, "error": "无法获取结果"}
                        
                        # 如果任务仍在运行，继续等待
                        if status in ["pending", "running"]:
                            logger.debug(f"Task {task_id} still {status}, waiting...")
                            await asyncio.sleep(1)
                            continue
                    
                    # 其他状态或请求失败，等待后重试
                    await asyncio.sleep(1)
                    
                except Exception:
                    # 请求异常，等待后重试
                    await asyncio.sleep(1)
            
            # 超时返回
            return {"status": "timeout", "error": "等待任务完成超时"} 