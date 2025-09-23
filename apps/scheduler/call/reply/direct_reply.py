# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""直接回复工具"""

import logging
import re
import base64
from collections.abc import AsyncGenerator
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import Field

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.reply.schema import DirectReplyInput, DirectReplyOutput
from apps.schemas.enum_var import CallOutputType, CallType, LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.scheduler.variable import get_pool_manager
from apps.scheduler.variable.type import VariableScope, VariableType
from apps.common.minio import MinioClient
from apps.common.mongo import MongoDB

logger = logging.getLogger(__name__)


class DirectReply(CoreCall, input_model=DirectReplyInput, output_model=DirectReplyOutput):
    """直接回复工具，支持变量引用语法"""

    to_user: bool = Field(default=True)
    controlled_output: bool = Field(default=True)
    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "直接回复",
            "type": CallType.DEFAULT,
            "description": "直接回复用户输入的内容，支持变量插入",
        },
        LanguageType.ENGLISH: {
            "name": "DirectReply",
            "type": CallType.DEFAULT,
            "description": "Reply contents defined by user, with inserted reference variables",
        },
    }

    async def _init(self, call_vars: CallVars) -> DirectReplyInput:
        """初始化DirectReply工具"""
        answer = getattr(self, 'answer', '')
        attachment = getattr(self, 'attachment', None)
        return DirectReplyInput(answer=answer, attachment=attachment)

    async def _parse_variable_references(self, attachment_dict: Dict[str, Dict[str, str]]) -> Dict[str, List[str]]:
        """解析附件变量引用，返回变量名到文件ID列表的映射"""
        variable_file_map = {}
        pool_manager = await get_pool_manager()
        
        for var_name, var_info in attachment_dict.items():
            # 获取完整的displayName，如 "conversation.file"
            display_name = var_info.get('displayName', f"conversation.{var_name}")
            
            # 解析displayName获取scope和实际变量名
            parts = display_name.split('.')
            if len(parts) >= 2:
                scope_str = parts[0]
                actual_var_name = parts[-1]  # 取最后一部分作为实际变量名
            else:
                logger.warning(f"[DirectReply] 无效的变量路径: {display_name}")
                continue
            
            # 确定变量作用域
            try:
                scope = VariableScope(scope_str)
            except ValueError:
                logger.warning(f"[DirectReply] 无效的变量作用域: {scope_str}")
                continue
            
            # 从变量池中获取变量
            variable = await pool_manager.get_variable_from_any_pool(
                name=actual_var_name,
                scope=scope,
                user_id=getattr(self._sys_vars.ids, 'user_sub', None),
                flow_id=getattr(self._sys_vars.ids, 'flow_id', None),
                conversation_id=getattr(self._sys_vars.ids, 'conversation_id', None)
            )
            
            if variable is None:
                logger.warning(f"[DirectReply] 变量不存在: {display_name} (scope: {scope_str}, name: {actual_var_name})")
                continue
                
            # 检查是否为文件类型变量
            if variable.var_type not in [VariableType.FILE, VariableType.ARRAY_FILE]:
                logger.warning(f"[DirectReply] 变量不是文件类型: {display_name}, 类型: {variable.var_type}")
                continue
                
            # 提取文件ID
            file_ids = []
            value = variable.value
            
            if variable.var_type == VariableType.FILE:
                # 单文件变量
                if isinstance(value, str):
                    file_ids.append(value)
                elif isinstance(value, dict) and "file_id" in value:
                    file_ids.append(value["file_id"])
            elif variable.var_type == VariableType.ARRAY_FILE:
                # 多文件变量
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            file_ids.append(item)
                        elif isinstance(item, dict) and "file_id" in item:
                            file_ids.append(item["file_id"])
                elif isinstance(value, dict) and "file_ids" in value:
                    file_ids.extend(value["file_ids"])
            
            if file_ids:
                variable_file_map[display_name] = file_ids
                logger.info(f"[DirectReply] 提取到文件变量 {display_name}: {len(file_ids)} 个文件")
            else:
                logger.warning(f"[DirectReply] 文件变量 {display_name} 中没有有效的文件ID")
        
        return variable_file_map
    
    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行直接回复"""
        data = DirectReplyInput(**input_data)
        
        try:
            # 使用基类的变量解析功能处理文本中的变量引用
            final_answer = await self._resolve_variables_in_text(data.answer, self._sys_vars)
            
            logger.info(f"[DirectReply] 原始答案: {data.answer}")
            logger.info(f"[DirectReply] 解析后答案: {final_answer}")
            
            # 首先返回文本内容
            yield CallOutputChunk(
                type=CallOutputType.TEXT, 
                content=final_answer
            )
            
            # 处理附件
            if data.attachment:
                logger.info(f"[DirectReply] 开始处理附件: {data.attachment}")
                
                # 解析变量引用并提取文件ID
                variable_file_map = await self._parse_variable_references(data.attachment)
                
                if variable_file_map:
                    # 🔑 重要修改：按变量分组处理文件，支持array[file]类型
                    for var_name, file_ids in variable_file_map.items():
                        if len(file_ids) == 1:
                            # 单文件：使用原有的单独返回方式
                            file_id = file_ids[0]
                            try:
                                # 从MongoDB获取文件信息
                                mongo = MongoDB()
                                doc_collection = mongo.get_collection("document")
                                doc_info = await doc_collection.find_one({"_id": file_id})
                                if not doc_info:
                                    logger.warning(f"[DirectReply] 文件信息不存在: {file_id}")
                                    continue
                                
                                filename = doc_info.get("name", f"file_{file_id}")
                                file_size = doc_info.get("size", 0)
                                file_type = doc_info.get("type", "application/octet-stream")
                                
                                # 从MinIO下载文件数据
                                try:
                                    metadata, file_data = MinioClient.download_file("document", file_id)
                                    
                                    # 从metadata中获取原始文件名（如果存在）
                                    if "file_name" in metadata:
                                        try:
                                            original_filename = base64.b64decode(metadata["file_name"]).decode('utf-8')
                                            filename = original_filename
                                        except Exception:
                                            pass  # 使用默认文件名
                                    
                                    # 将文件数据编码为base64
                                    file_content_b64 = base64.b64encode(file_data).decode('utf-8')
                                    
                                    # 单个文件：使用FILE类型
                                    yield CallOutputChunk(
                                        type=CallOutputType.FILE,
                                        content={
                                            "file_id": file_id,
                                            "filename": filename,
                                            "file_type": file_type,
                                            "file_size": file_size,
                                            "content": file_content_b64,
                                            "variable_name": var_name
                                        }
                                    )
                                    logger.info(f"[DirectReply] 成功返回单文件: {var_name}/{filename} (ID: {file_id})")
                                    
                                except Exception as minio_error:
                                    logger.error(f"[DirectReply] 从MinIO下载文件失败: {file_id}, 错误: {minio_error}")
                                    continue
                                    
                            except Exception as file_error:
                                logger.error(f"[DirectReply] 处理文件失败: {file_id}, 错误: {file_error}")
                                continue
                        
                        elif len(file_ids) > 1:
                            # 多文件：合并为一个FILES类型的响应
                            files_data = []
                            
                            for file_id in file_ids:
                                try:
                                    # 从MongoDB获取文件信息
                                    mongo = MongoDB()
                                    doc_collection = mongo.get_collection("document")
                                    doc_info = await doc_collection.find_one({"_id": file_id})
                                    if not doc_info:
                                        logger.warning(f"[DirectReply] 文件信息不存在: {file_id}")
                                        continue
                                    
                                    filename = doc_info.get("name", f"file_{file_id}")
                                    file_size = doc_info.get("size", 0)
                                    file_type = doc_info.get("type", "application/octet-stream")
                                    
                                    # 从MinIO下载文件数据
                                    try:
                                        metadata, file_data = MinioClient.download_file("document", file_id)
                                        
                                        # 从metadata中获取原始文件名（如果存在）
                                        if "file_name" in metadata:
                                            try:
                                                original_filename = base64.b64decode(metadata["file_name"]).decode('utf-8')
                                                filename = original_filename
                                            except Exception:
                                                pass  # 使用默认文件名
                                        
                                        # 将文件数据编码为base64
                                        file_content_b64 = base64.b64encode(file_data).decode('utf-8')
                                        
                                        files_data.append({
                                            "file_id": file_id,
                                            "filename": filename,
                                            "file_type": file_type,
                                            "file_size": file_size,
                                            "content": file_content_b64,
                                            "variable_name": var_name
                                        })
                                        
                                    except Exception as minio_error:
                                        logger.error(f"[DirectReply] 从MinIO下载文件失败: {file_id}, 错误: {minio_error}")
                                        continue
                                        
                                except Exception as file_error:
                                    logger.error(f"[DirectReply] 处理文件失败: {file_id}, 错误: {file_error}")
                                    continue
                            
                            # 如果有成功处理的文件，返回FILES类型
                            if files_data:
                                yield CallOutputChunk(
                                    type=CallOutputType.FILE,
                                    content={
                                        "type": "files",
                                        "variable_name": var_name,
                                        "files": files_data
                                    }
                                )
                                logger.info(f"[DirectReply] 成功返回多文件: {var_name} ({len(files_data)} 个文件)")
                else:
                    logger.warning("[DirectReply] 没有找到有效的文件变量")
            
        except Exception as e:
            logger.error(f"[DirectReply] 处理回复内容失败: {e}")
            raise CallError(
                message=f"直接回复处理失败：{e!s}", 
                data={"original_answer": data.answer, "attachment": data.attachment}
            ) from e
