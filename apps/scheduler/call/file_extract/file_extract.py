# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件提取器Call"""

import asyncio
import json
import logging
import re
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, ClassVar

import httpx

from apps.common.config import Config
from apps.common.minio import MinioClient
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.file_extract.schema import FileExtractInput, FileExtractOutput
from apps.scheduler.variable.pool_manager import get_pool_manager
from apps.scheduler.variable.type import VariableType
from apps.schemas.enum_var import CallType, LanguageType
from apps.schemas.scheduler import CallInfo, CallVars, CallOutputChunk, CallOutputType, CallError
from pydantic import Field

logger = logging.getLogger(__name__)


class FileExtract(CoreCall, input_model=FileExtractInput, output_model=FileExtractOutput):
    """文件提取器Call"""
    i18n_info: ClassVar[dict[str, dict]] = {
        LanguageType.CHINESE: {
            "name": "文件提取器",
            "type": CallType.TRANSFORM,
            "description": "从文件中提取文本内容，支持多种文件格式的解析",
        },
        LanguageType.ENGLISH: {
            "name": "FileExtract",
            "type": CallType.TRANSFORM,
            "description": "Extract text content from different kinds of document",
        },
    }

    controlled_output: bool = Field(default=True)
    # 添加output_parameters字段支持
    output_parameters: dict[str, Any] = Field(description="输出参数配置", default={
        "text": {"type": "string", "description": "提取的文本内容"},
        "error": {"type": "string", "description": "错误信息"},
        "report": {"type": "string", "description": "详细处理报告"}
    })
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _simple_file_type_detection(self, file_data: bytes) -> str:
        """
        简化的文件类型检测，只检测最常见的几种类型
        
        :param file_data: 文件二进制数据
        :return: 检测到的文件扩展名，如果无法检测则返回None
        """
        if len(file_data) < 4:
            return None
        
        # 获取文件头
        header = file_data[:16]
        
        try:
            # PDF文件
            if header.startswith(b'%PDF'):
                return "pdf"
            
            # PNG图片
            if header.startswith(b'\x89PNG\r\n\x1a\n'):
                return "png"
            
            # JPEG图片
            if header.startswith(b'\xff\xd8\xff'):
                return "jpg"
            
            # GIF图片
            if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
                return "gif"
            
            # BMP图片
            if header.startswith(b'BM'):
                return "bmp"
            
            # ZIP文件/Office文档（简化检测）
            if header.startswith(b'PK\x03\x04') or header.startswith(b'PK\x05\x06') or header.startswith(b'PK\x07\x08'):
                # 检查是否是Office文档
                sample = file_data[:2000]  # 检查前2KB
                if b'word/' in sample or b'[Content_Types].xml' in sample:
                    return "docx"
                elif b'xl/' in sample:
                    return "xlsx"
                elif b'ppt/' in sample:
                    return "pptx"
                else:
                    return "zip"
            
            # 简单的文本文件检测
            try:
                # 尝试解码前1024字节
                sample = file_data[:1024]
                
                # 检查是否包含NULL字节（二进制文件的强指示）
                if b'\x00' in sample:
                    return None  # 包含NULL字节，很可能是二进制文件
                
                decoded = sample.decode('utf-8')
                
                # 检查是否包含HTML标记
                if any(marker in decoded.lower() for marker in ['<html', '<!doctype', '<?xml']):
                    return "html"
                
                # 检查是否是JSON
                if decoded.strip().startswith(('{', '[')):
                    return "json"
                
                # 检查是否是Markdown
                if decoded.startswith('#') or '\n# ' in decoded or '\n## ' in decoded:
                    return "md"
                
                # 如果能解码且看起来像文本，返回txt
                if len(decoded.strip()) > 0:
                    return "txt"
                    
            except UnicodeDecodeError:
                # 无法解码为UTF-8，可能是二进制文件
                pass
            
            # 无法识别
            return None
            
        except Exception as e:
            logger.warning(f"文件类型检测时发生错误: {e}")
            return None

    def _extract_error_info(self, e: Exception) -> tuple[str, str]:
        """
        提取异常的错误信息和详细信息
        
        :param e: 异常对象
        :return: (错误消息, 详细信息)
        """
        if isinstance(e, CallError):
            error_msg = e.message
            error_details = f"错误信息: {e.message}"
            if e.data:
                error_details += f"\n错误数据: {e.data}"
        else:
            error_msg = str(e) if str(e) else f"未知错误: {type(e).__name__}"
            error_details = f"错误信息: {error_msg}\n错误类型: {type(e).__name__}"
        
        return error_msg, error_details

    async def _init(self, call_vars: CallVars) -> FileExtractInput:
        """
        初始化Call

        :param CallVars call_vars: 由Executor传入的变量，包含当前运行信息
        :return: Call的输入
        :rtype: FileExtractInput
        """
        # 保存CallVars以便在_exec中使用
        self._call_vars = call_vars
        
        # 从实例属性中获取参数
        parse_method = getattr(self, 'parse_method', '')
        target = getattr(self, 'target', '')
        
        return FileExtractInput(
            parse_method=parse_method,
            target=target,
        )

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """
        执行文件提取操作

        :param dict[str, Any] input_data: 填充后的Call的最终输入
        """
        try:
            parse_method = input_data.get('parse_method', '')
            target = input_data.get('target', '')
            
            if not parse_method:
                raise CallError(
                    message="解析方法不能为空",
                    data={"parse_method": parse_method, "input_data": input_data}
                )
            
            if not target:
                raise CallError(
                    message="目标文件变量不能为空",
                    data={"target": target, "input_data": input_data}
                )
            
            # 解析变量引用，获取文件数据
            call_vars = self._call_vars
            file_variable = await self._resolve_file_variable(target, call_vars)
            
            if not file_variable:
                raise CallError(
                    message=f"无法找到目标文件变量: {target}",
                    data={"target": target}
                )
            
            # 检查变量类型
            var_type = file_variable.var_type
            if var_type not in [VariableType.FILE, VariableType.ARRAY_FILE]:
                raise CallError(
                    message=f"变量类型不支持，期望 file 或 array[file]，实际: {var_type}",
                    data={"target": target, "var_type": str(var_type)}
                )
            
            # 处理文件
            report_info = ""
            if var_type == VariableType.FILE:
                # 单个文件 - 需要从变量值中提取文件ID
                if isinstance(file_variable.value, dict):
                    # 如果是字典格式，提取file_id字段
                    file_id = file_variable.value.get('file_id')
                    if not file_id:
                        raise CallError(
                            message="文件变量格式错误：缺少file_id字段",
                            data={"file_variable_value": file_variable.value}
                        )
                elif isinstance(file_variable.value, str):
                    # 如果是字符串格式，直接使用
                    file_id = file_variable.value
                else:
                    raise CallError(
                        message=f"文件变量格式不支持：{type(file_variable.value)}",
                        data={"file_variable_value": file_variable.value}
                    )
                
                text_content, report_info = await self._process_single_file(file_id, parse_method, call_vars, file_variable)
            else:
                # 文件数组 - 从变量值中提取file_ids
                if isinstance(file_variable.value, dict) and 'file_ids' in file_variable.value:
                    file_ids = file_variable.value['file_ids']
                    text_content, report_info = await self._process_file_array(file_ids, parse_method, call_vars, file_variable)
                else:
                    # 兼容性处理：如果值就是文件ID列表或单个文件ID
                    if isinstance(file_variable.value, list):
                        file_ids = file_variable.value
                    elif isinstance(file_variable.value, str):
                        file_ids = [file_variable.value]
                    elif isinstance(file_variable.value, dict) and 'file_id' in file_variable.value:
                        # 如果是单个文件字典格式，提取file_id并转为列表
                        file_ids = [file_variable.value['file_id']]
                    else:
                        raise CallError(
                            message=f"数组文件变量格式不支持：{type(file_variable.value)}",
                            data={"file_variable_value": file_variable.value}
                        )
                    text_content, report_info = await self._process_file_array(file_ids, parse_method, call_vars, file_variable)
            
            # 将结果存储到对话级变量池（基于conversation_id的实际对话变量）
            await self._save_result_to_conversation_pool(text_content, call_vars)
            
            # 返回结果
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=FileExtractOutput(text=text_content, report=report_info).model_dump(by_alias=True, exclude_none=True)
            )
                
        except Exception as e:
            if isinstance(e, CallError):
                # 重新抛出 CallError，让步骤失败
                logger.error(f"文件提取失败: {e.message}")
                raise
            else:
                logger.error(f"文件提取操作失败: {e}", exc_info=True)
                raise CallError(
                    message=f"文件提取操作失败: {str(e)}。请检查文件是否可正常访问，或联系管理员。",
                    data={"error_type": type(e).__name__}
                ) from e

    async def _resolve_file_variable(self, target: str, call_vars: CallVars):
        """
        解析文件变量引用
        
        :param target: 变量引用字符串，如 {{file_var}}
        :param call_vars: 调用上下文
        :return: 变量对象
        """
        try:
            # 解析变量引用格式 {{variable_name}}
            match = re.match(r'^\{\{(.+)\}\}$', target.strip())
            if not match:
                raise CallError(
                    message=f"无效的变量引用格式: {target}，应为 {{{{variable_name}}}}",
                    data={"target": target}
                )
            
            variable_ref = match.group(1).strip()
            
            # 解析变量作用域和名称 (支持 conversation.name, user.name, flow.name 格式)
            if '.' in variable_ref:
                scope, variable_name = variable_ref.split('.', 1)
            else:
                scope = None
                variable_name = variable_ref
            
            # 从变量池中获取变量
            pool_manager = await get_pool_manager()
            
            # 根据作用域决定查找策略
            if scope == 'conversation':
                # 明确指定从对话变量池查找
                if call_vars.ids.conversation_id:
                    conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
                    if conversation_pool:
                        variable = await conversation_pool.get_variable(variable_name)
                        if variable:
                            return variable
                
            elif scope == 'user':
                # 明确指定从用户变量池查找
                if call_vars.ids.user_sub:
                    user_pool = await pool_manager.get_user_pool(call_vars.ids.user_sub)
                    if user_pool:
                        variable = await user_pool.get_variable(variable_name)
                        if variable:
                            return variable
                    
            elif scope == 'flow':
                # 明确指定从流程变量池查找
                if call_vars.ids.flow_id:
                    flow_pool = await pool_manager.get_flow_pool(call_vars.ids.flow_id)
                    if flow_pool:
                        variable = await flow_pool.get_variable(variable_name)
                        if variable:
                            return variable
                    
            else:
                # 没有指定作用域，按优先级顺序查找：对话 -> 用户 -> 流程
                # 首先尝试从对话变量池中获取
                if call_vars.ids.conversation_id:
                    conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
                    if conversation_pool:
                        variable = await conversation_pool.get_variable(variable_name)
                        if variable:
                            return variable
                
                # 如果对话变量池中没有，尝试从用户变量池中获取
                if call_vars.ids.user_sub:
                    user_pool = await pool_manager.get_user_pool(call_vars.ids.user_sub)
                    if user_pool:
                        variable = await user_pool.get_variable(variable_name)
                        if variable:
                            return variable
                
                # 如果用户变量池中也没有，尝试从环境变量池中获取
                if call_vars.ids.flow_id:
                    flow_pool = await pool_manager.get_flow_pool(call_vars.ids.flow_id)
                    if flow_pool:
                        variable = await flow_pool.get_variable(variable_name)
                        if variable:
                            return variable
            
            return None
            
        except Exception as e:
            logger.error(f"解析文件变量失败: {e}")
            raise CallError(
                message=f"解析文件变量失败: {e}",
                data={"target": target}
            ) from e

    async def _process_single_file(self, file_id: str, parse_method: str, call_vars: CallVars, file_variable: Any) -> tuple[str, str]:
        """
        处理单个文件
        
        :param file_id: 文件ID
        :param parse_method: 解析方法
        :param call_vars: 调用上下文
        :return: 提取的文本内容和报告信息
        """
        try:
            logger.info(f"开始处理单个文件: {file_id}")
            # 从MinIO下载文件
            metadata, file_data = MinioClient.download_file("document", file_id)
            logger.info(f"文件下载成功: 大小={len(file_data)}字节, 元数据={metadata}")
            
            # 尝试从文件变量中获取原始文件名
            original_filename = None
            if file_variable and hasattr(file_variable, 'value'):
                logger.info(f"文件变量类型: {type(file_variable)}, 值类型: {type(file_variable.value)}")
                
                # 🔧 使用新的辅助函数获取文件名（兼容新旧格式）
                if isinstance(file_variable.value, dict):
                    # 导入辅助函数
                    from apps.scheduler.variable.file_utils import FileVariableHelper
                    
                    # 使用统一的接口获取文件名
                    original_filename = FileVariableHelper.get_filename_by_file_id(file_variable.value, file_id)
                    if original_filename:
                        logger.info(f"✓ 通过辅助函数获取文件名: {original_filename}")
                    else:
                        # 兼容性回退：尝试其他可能的字段
                        original_filename = (
                            file_variable.value.get('original_filename') or
                            file_variable.value.get('name') or 
                            file_variable.value.get('file_name')
                        )
                        if original_filename:
                            logger.info(f"○ 从兼容字段获取文件名: {original_filename}")
                    
                    logger.debug(f"文件变量字典内容: {file_variable.value}")
                
                # 检查是否有to_string方法（FileVariable的方法）
                if hasattr(file_variable, 'to_string') and not original_filename:
                    try:
                        filename_from_tostring = file_variable.to_string()
                        # 避免使用默认的file_id作为文件名
                        if filename_from_tostring and not filename_from_tostring.startswith('file_') and '.' in filename_from_tostring:
                            original_filename = filename_from_tostring
                            logger.info(f"○ 从文件变量to_string()获取文件名: {original_filename}")
                    except Exception as e:
                        logger.warning(f"调用文件变量to_string()方法失败: {e}")
            
            # 获取文件名 - 优先使用文件变量中的原始文件名
            if original_filename and original_filename.strip():
                filename = original_filename.strip()
                logger.info(f"✓ 使用文件变量中的原始文件名: {filename}")
            else:
                # 回退到MinIO元数据中的文件名
                filename = metadata.get("file_name", f"file_{file_id}")
                if isinstance(filename, str) and filename.startswith("data:"):
                    # 如果是base64编码的文件名，需要解码
                    import base64
                    try:
                        filename = base64.b64decode(filename.split(',')[1]).decode('utf-8')
                        logger.info(f"✓ 解码base64文件名: {filename}")
                    except Exception as e:
                        filename = f"file_{file_id}"
                        logger.warning(f"base64解码失败: {e}, 使用默认文件名: {filename}")
                logger.info(f"○ 使用MinIO元数据中的文件名: {filename}")
            
            # 现在基于原始文件名的扩展名来处理
            file_extension = Path(filename).suffix
            if not file_extension:
                logger.warning(f"文件没有扩展名: {filename}，尝试其他方法确定文件类型")
                
                # 当没有扩展名时，根据parse_method参数来推断可能的文件类型
                suggested_extensions = []
                if parse_method.lower() in ['ocr']:
                    suggested_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'pdf']
                elif parse_method.lower() in ['general', 'enhanced', 'deep', 'fine']:
                    suggested_extensions = ['pdf', 'docx', 'txt', 'md', 'html']
                else:
                    suggested_extensions = ['txt', 'pdf', 'docx']
                
                # 检查文件内容的前几个字节来猜测文件类型
                detected_type = self._simple_file_type_detection(file_data)
                if detected_type:
                    filename = f"{filename}.{detected_type}"
                    logger.info(f"✓ 基于文件内容检测，添加扩展名: {filename}")
                else:
                    # 如果无法检测，给出明确的错误信息
                    suggested_ext_str = ', '.join(f'.{ext}' for ext in suggested_extensions)
                    raise CallError(
                        message=f"文件 '{filename}' 没有扩展名且无法自动检测文件类型。请确保文件有正确的扩展名。",
                        data={
                            "file_id": file_id,
                            "filename": filename,
                            "parse_method": parse_method,
                            "suggested_extensions": suggested_ext_str,
                            "suggestion": f"基于解析方法 '{parse_method}'，建议的文件格式：{suggested_ext_str}"
                        }
                    )
            else:
                logger.info(f"✓ 文件扩展名: {file_extension}")
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            logger.info(f"临时文件创建: {temp_file_path}")
            
            try:
                # 调用RAG服务进行文件解析
                text_content, report_info = await self._parse_file_with_rag(
                    temp_file_path, filename, parse_method, call_vars
                )
                logger.info(f"RAG解析完成: 文本长度={len(text_content) if text_content else 0}, 报告长度={len(report_info) if report_info else 0}")
                return text_content, report_info
            finally:
                # 清理临时文件
                Path(temp_file_path).unlink(missing_ok=True)
                logger.debug(f"临时文件清理完成: {temp_file_path}")
                
        except Exception as e:
            logger.error(f"处理单个文件失败: {e}", exc_info=True)
            if isinstance(e, CallError):
                # 如果已经是CallError，直接重新抛出
                raise
            else:
                raise CallError(
                    message=f"处理文件失败: {e}",
                    data={"file_id": file_id, "error_type": type(e).__name__}
                ) from e

    async def _process_file_array(self, file_list: list, parse_method: str, call_vars: CallVars, file_variable: Any) -> tuple[str, str]:
        """
        处理文件数组
        
        :param file_list: 文件ID列表
        :param parse_method: 解析方法
        :param call_vars: 调用上下文
        :return: 提取的文本内容（多个文件内容合并）和报告信息
        """
        try:
            all_text_content = []
            failed_files = []
            all_reports = []  # 收集所有文件的报告信息
            
            for i, file_id in enumerate(file_list):
                try:
                    logger.info(f"开始处理文件 {i+1}/{len(file_list)}: {file_id}")
                    text_content, report_info = await self._process_single_file(file_id, parse_method, call_vars, file_variable)
                    
                    # 记录处理结果
                    text_length = len(text_content.strip()) if text_content else 0
                    logger.info(f"文件 {i+1} 处理完成: 提取文本长度={text_length}, 报告长度={len(report_info) if report_info else 0}")
                    
                    if text_content.strip():
                        all_text_content.append(f"=== 文件 {i+1} ===\n{text_content}")
                    
                    # 收集报告信息
                    if report_info:
                        all_reports.append(f"=== 文件 {i+1} 处理报告 ===\n{report_info}")
                        logger.debug(f"文件 {i+1} 报告: {report_info}")  # 移除长度限制
                    else:
                        default_report = "处理成功，无详细报告"
                        all_reports.append(f"=== 文件 {i+1} 处理报告 ===\n{default_report}")
                        logger.info(f"文件 {i+1} {default_report}")
                        
                except Exception as e:
                    # 使用辅助方法正确提取错误信息
                    error_msg, error_details = self._extract_error_info(e)
                    
                    logger.error(f"处理文件 {file_id} 失败: {error_msg}", exc_info=True)
                    
                    failed_files.append(f"文件 {i+1}（ID: {file_id}）: {error_msg}")
                    error_report = f"处理失败: {error_details}"
                    all_reports.append(f"=== 文件 {i+1} 处理报告 ===\n{error_report}")
                    continue
            
            # 构建结果信息
            logger.info(f"文件数组处理完成: 总文件数={len(file_list)}, 成功提取文本的文件数={len(all_text_content)}, 失败文件数={len(failed_files)}")
            
            result_parts = []
            if all_text_content:
                combined_text = "\n\n".join(all_text_content)
                result_parts.append(combined_text)
                logger.info(f"合并文本内容: 总长度={len(combined_text)}")
            
            if failed_files:
                failed_info = f"\n\n=== 处理失败的文件 ===\n" + "\n".join(failed_files)
                result_parts.append(failed_info)
                logger.warning(f"处理失败文件信息: {failed_info}")
            
            # 构建完整的报告信息
            complete_report = "\n\n".join(all_reports) if all_reports else "无处理报告"
            logger.info(f"生成完整报告: 长度={len(complete_report)}")
            # logger.info(f"完整报告内容: {complete_report[:500]}...")
            logger.info(f"完整报告内容: {complete_report}")
            
            # 只有当存在失败文件时才抛出错误，提取结果为空字符串是正常情况
            if failed_files:
                logger.error(f"部分文件处理失败，抛出CallError: 成功={len(file_list) - len(failed_files)}, 失败={len(failed_files)}")
                raise CallError(
                    message=f"部分文件处理失败。成功文件数: {len(file_list) - len(failed_files)}, 失败文件数: {len(failed_files)}",
                    data={
                        "total_files": len(file_list),
                        "successful_files": len(file_list) - len(failed_files),
                        "failed_files": len(failed_files),
                        "failed_details": failed_files,
                        "report": complete_report
                    }
                )
            
            final_result = "\n\n".join(result_parts) if result_parts else ""
            logger.info(f"文件数组处理成功: 最终结果长度={len(final_result)}, 报告长度={len(complete_report)}")
            return final_result, complete_report
            
        except Exception as e:
            if isinstance(e, CallError):
                raise  # 重新抛出CallError
            
            # 对于非CallError，提取正确的错误信息
            error_msg = str(e) if str(e) else f"未知错误: {type(e).__name__}"
            logger.error(f"处理文件数组失败: {error_msg}", exc_info=True)
            raise CallError(
                message=f"处理文件数组失败: {error_msg}",
                data={"file_count": len(file_list), "error_type": type(e).__name__}
            ) from e

    async def _parse_file_with_rag(self, file_path: str, filename: str, parse_method: str, call_vars: CallVars) -> tuple[str, str]:
        """
        使用RAG服务解析文件
        
        :param file_path: 临时文件路径
        :param filename: 原始文件名
        :param parse_method: 解析方法
        :param call_vars: 调用上下文
        :return: 解析的文本内容和报告信息
        """
        try:
            # 获取RAG服务配置
            config = Config().get_config()
            rag_host = config.rag.rag_service.rstrip("/")
            
            # 生成临时文档ID
            doc_id = str(uuid.uuid4())
            logger.info(f"生成临时文档ID: {doc_id}, 文件: {filename}")
            
            # 上传文件到MinIO临时存储
            temp_bucket = "temporary"
            MinioClient.check_bucket(temp_bucket)
            
            # 上传文件
            with open(file_path, 'rb') as f:
                MinioClient.upload_file(
                    bucket_name=temp_bucket,
                    object_name=doc_id,
                    data=f,
                    length=-1,
                    part_size=10*1024*1024,
                    metadata={"original_filename": filename}
                )
            
            logger.info(f"文件上传到MinIO成功: bucket={temp_bucket}, object={doc_id}")
            
            try:
                # 调用RAG解析接口
                session_id = call_vars.ids.session_id or call_vars.ids.conversation_id or "temp_session"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {session_id}",
                }
                
                logger.info(f"准备调用RAG解析: session_id={session_id}")
                
                # 请求解析，使用正确的字段名称和格式
                # 获取文件扩展名
                file_extension = Path(filename).suffix.lstrip('.') if Path(filename).suffix else "txt"
                
                parse_data = {
                    "document_list": [{
                        "id": doc_id,
                        "name": filename,
                        "bucket_name": temp_bucket,
                        "type": file_extension,  # 文件扩展名
                        "parse_method": parse_method  # 修正字段名称
                    }]
                }
                
                logger.info(f"RAG解析请求数据: {parse_data}")
                
                async with httpx.AsyncClient() as client:
                    # 发起解析请求
                    parse_url = f"{rag_host}/doc/temporary/parser"
                    logger.info(f"发送解析请求到: {parse_url}")
                    parse_resp = await client.post(parse_url, headers=headers, json=parse_data, timeout=30.0)
                    
                    logger.info(f"解析请求响应: status={parse_resp.status_code}")
                    if parse_resp.status_code != 200:
                        logger.error(f"RAG解析请求失败: {parse_resp.status_code}, 响应: {parse_resp.text}")
                        raise CallError(
                            message=f"RAG解析请求失败: {parse_resp.status_code}",
                            data={"response": parse_resp.text}
                        )
                    
                    parse_result = parse_resp.json()
                    logger.info(f"解析请求结果: {parse_result}")
                    task_ids = parse_result.get("result", [])
                    
                    if not task_ids:
                        logger.error(f"RAG解析请求未返回任务ID: {parse_result}")
                        raise CallError(
                            message="RAG解析请求未返回任务ID",
                            data={"response": parse_result}
                        )
                    
                    task_id = task_ids[0] if isinstance(task_ids, list) else task_ids
                    logger.info(f"获得任务ID: {task_id}")
                    
                    # 轮询解析状态
                    max_retries = 60  # 最多等待10分钟（每次等待10秒）
                    logger.info(f"开始轮询解析状态，最大重试次数: {max_retries}")
                    for attempt in range(max_retries):
                        await asyncio.sleep(10)  # 等待10秒
                        
                        status_url = f"{rag_host}/doc/temporary/status"
                        status_data = {"ids": [task_id]}
                        status_resp = await client.post(status_url, headers=headers, json=status_data, timeout=30.0)
                        
                        if status_resp.status_code != 200:
                            logger.warning(f"查询解析状态失败 (尝试 {attempt+1}): {status_resp.status_code}")
                            continue
                        
                        status_result = status_resp.json()
                        status_items = status_result.get("result", [])
                        
                        if not status_items:
                            logger.warning(f"状态查询无结果 (尝试 {attempt+1})")
                            continue
                        
                        status_item = status_items[0]
                        status = status_item.get("status")
                        logger.info(f"解析状态 (尝试 {attempt+1}): {status}")
                        
                        if status == "success":
                            # 解析成功，获取详细报告和文档全文
                            logger.info("解析成功，开始获取报告和文档全文")
                            report_info = ""
                            try:
                                report_info = await self._get_detailed_error_report(rag_host, task_id, headers, client)
                                if not report_info:
                                    report_info = "解析成功，无详细报告"
                                logger.info(f"获得处理报告: {report_info}")  # 移除长度限制
                            except Exception as e:
                                report_info = "无法获取详细报告"
                                logger.warning(f"获取处理报告失败: {e}")
                            
                            # 使用新的/doc/full_text接口获取文档全文
                            full_text_url = f"{rag_host}/doc/temporary/text"
                            full_text_params = {"id": task_id}
                            
                            logger.info(f"获取文档全文: {full_text_url}")
                            full_text_resp = await client.get(full_text_url, headers=headers, params=full_text_params, timeout=30.0)
                            
                            if full_text_resp.status_code != 200:
                                error_text = full_text_resp.text
                                logger.error(f"获取文档全文失败: {full_text_resp.status_code}, 响应: {error_text}")
                                raise CallError(
                                    message=f"获取文档全文失败: {full_text_resp.status_code}",
                                    data={"response": error_text, "task_id": task_id, "report": report_info}
                                )
                            
                            full_text_result = full_text_resp.json()
                            text_content = full_text_result.get("result", "")
                            
                            logger.info(f"文档全文获取成功: 长度={len(text_content) if text_content else 0}")
                            return text_content, report_info
                        
                        elif status == "failed":
                            logger.error(f"文件解析失败: {status_item}")
                            error_msg = status_item.get("error", "文件解析失败")
                            
                            # 获取详细的错误报告
                            detailed_error = ""
                            try:
                                detailed_error = await self._get_detailed_error_report(rag_host, task_id, headers, client)
                                if detailed_error:
                                    error_msg = detailed_error
                                logger.info(f"获得详细错误报告: {detailed_error}")  # 移除长度限制
                            except Exception as e:
                                logger.warning(f"获取详细错误报告失败: {e}")
                            
                            raise CallError(
                                message=f"文件解析失败: {error_msg}。请检查文件格式是否支持，或尝试重新上传文件。",
                                data={
                                    "task_id": task_id, 
                                    "status": status_item, 
                                    "filename": filename,
                                    "report": detailed_error or "无法获取详细报告"
                                }
                            )
                        
                        # status == "pending" 或 "running"，继续等待
                    
                    # 超时
                    logger.error(f"RAG文件解析超时: task_id={task_id}, 重试次数={max_retries}")
                    raise CallError(
                        message="RAG文件解析超时",
                        data={"task_id": task_id, "max_retries": max_retries}
                    )
            
            finally:
                # 清理临时文件
                try:
                    MinioClient.delete_file(temp_bucket, doc_id)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")
                
        except Exception as e:
            if isinstance(e, CallError):
                raise
            else:
                # 对于非CallError，提取正确的错误信息
                error_msg = str(e) if str(e) else f"未知错误: {type(e).__name__}"
                logger.error(f"RAG解析文件失败: {error_msg}", exc_info=True)
                raise CallError(
                    message=f"RAG解析文件失败: {error_msg}",
                    data={"filename": filename, "error_type": type(e).__name__}
                ) from e

    async def _get_detailed_error_report(self, rag_host: str, task_id: str, headers: dict, client) -> str:
        """
        获取详细的错误报告
        
        :param rag_host: RAG服务地址
        :param task_id: 任务ID
        :param headers: 请求头
        :param client: HTTP客户端
        :return: 详细错误信息
        """
        try:
            report_url = f"{rag_host}/doc/report"
            report_params = {"docId": task_id}
            
            report_resp = await client.get(report_url, headers=headers, params=report_params, timeout=10.0)
            if report_resp.status_code == 200:
                report_result = report_resp.json()
                report_data = report_result.get("result", "")
                
                # 如果报告是字符串，解析其中的错误信息
                if isinstance(report_data, str) and report_data.strip():
                    # 提取最关键的错误信息
                    error_messages = []
                    
                    # 按行分割报告内容
                    lines = report_data.strip().split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        # 查找包含"错误信息"的行
                        if "错误信息:" in line:
                            # 提取错误信息部分
                            error_part = line.split("错误信息:")[-1].strip()
                            if error_part and error_part not in error_messages:
                                error_messages.append(error_part)
                        
                        # 查找包含"[BaseParser]"等关键错误标识的行
                        elif any(keyword in line for keyword in ["[BaseParser]", "[DocParseWorker]", "解析器不存在", "任务失败"]):
                            # 清理并提取有用信息
                            if "解析器不存在" in line:
                                parser_error = "解析器不存在，可能是文件格式不支持或解析方法配置错误"
                                if parser_error not in error_messages:
                                    error_messages.append(parser_error)
                            elif "任务失败" in line and "错误信息:" in line:
                                # 已经在上面处理了
                                continue
                    
                    if error_messages:
                        # 去重并组合错误信息
                        unique_errors = list(dict.fromkeys(error_messages))  # 保持顺序去重
                        return "; ".join(unique_errors)
                    else:
                        # 如果没有找到具体的错误信息，返回完整报告
                        return report_data  # 移除长度限制
                
                # 如果报告是字典格式
                elif isinstance(report_data, dict):
                    error_info = []
                    
                    if "error" in report_data and report_data["error"]:
                        error_info.append(f"错误: {report_data['error']}")
                    
                    if "message" in report_data and report_data["message"]:
                        error_info.append(f"详情: {report_data['message']}")
                    
                    if error_info:
                        return "; ".join(error_info)
            
            return None
            
        except Exception:
            return None

    async def _save_result_to_conversation_pool(self, text_content: str, call_vars: CallVars) -> None:
        """
        将提取的文本结果保存到对话级变量池（基于conversation_id的实际对话变量）
        
        :param text_content: 提取的文本内容
        :param call_vars: 调用上下文
        """
        try:
            if not call_vars.ids.conversation_id:
                logger.warning("没有conversation_id，无法保存到对话级变量池")
                return
            
            pool_manager = await get_pool_manager()
            conversation_pool = await pool_manager.get_conversation_pool(call_vars.ids.conversation_id)
            
            if not conversation_pool:
                logger.warning("无法获取对话级变量池")
                return
            
            # 构造变量名：step_id.text（与output_parameters格式保持一致）
            step_id = getattr(self, '_step_id', 'unknown')
            variable_name = f"{step_id}.text"
            
            # 保存变量 - 先尝试更新，如果不存在则添加
            try:
                # 尝试更新现有变量
                await conversation_pool.update_variable(
                    name=variable_name,
                    value=text_content
                )
            except (KeyError, ValueError):
                # 变量不存在，创建新变量
                await conversation_pool.add_variable(
                    name=variable_name,
                    var_type=VariableType.STRING,
                    value=text_content,
                    description="文件提取的文本内容"
                )
            
        except Exception as e:
            logger.error(f"保存结果到对话级变量池失败: {e}")
            # 不抛出异常，因为这不应该影响主要的执行流程
