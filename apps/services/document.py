# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件Manager"""

import base64
from datetime import UTC, datetime
import logging
import uuid
from typing import Optional

import asyncer
from fastapi import UploadFile

from apps.common.minio import MinioClient
from apps.common.mongo import MongoDB
from apps.common.config import Config
from apps.schemas.collection import (
    Conversation,
    Document,
)
from apps.schemas.record import RecordDocument, RecordGroup, RecordGroupDocument
from apps.services.knowledge_base import KnowledgeBaseService
from apps.services.session import SessionManager
from apps.scheduler.variable import get_pool_manager, VariableType, VariableScope, VariableMetadata, create_variable

logger = logging.getLogger(__name__)


class DocumentManager:
    """文件相关操作"""

    @classmethod
    def _storage_single_doc_minio(cls, file_id: str, document: UploadFile) -> str:
        """存储单个文件到MinIO"""
        MinioClient.check_bucket("document")
        file = document.file
        # 获取文件MIME
        import magic
        mime = magic.from_buffer(file.read(), mime=True)
        file.seek(0)

        # 上传到MinIO
        MinioClient.upload_file(
            bucket_name="document",
            object_name=file_id,
            data=file,
            content_type=mime,
            length=-1,
            part_size=10 * 1024 * 1024,
            metadata={
                # type: ignore[arg-type]
                "file_name": base64.b64encode(document.filename.encode("utf-8")).decode("ascii"),
            },
        )
        return mime

    @classmethod
    async def validate_file_upload_for_variable(cls, user_sub: str, documents: list[UploadFile], var_name: str, var_type: str, scope: str, conversation_id: Optional[str] = None, flow_id: Optional[str] = None) -> tuple[bool, str]:
        """验证文件上传是否符合变量限制"""
        try:
            logger.info(f"开始验证文件上传: scope={scope}, var_name={var_name}, conversation_id={conversation_id}, flow_id={flow_id}")
            pool_manager = await get_pool_manager()
            
            # 根据scope获取变量池
            if scope == "system":
                pool = await pool_manager.get_conversation_pool(conversation_id)
                if not pool:
                    # 兜底：如果conversation pool不存在，自动创建
                    if not flow_id:
                        flow_id = await cls._get_flow_id_for_conversation(conversation_id)
                    logger.info(f"自动创建system scope的conversation pool: {conversation_id}, flow_id={flow_id}")
                    pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
            elif scope == "user":
                pool = await pool_manager.get_user_pool(user_sub)
            elif scope == "env":
                pool = await pool_manager.get_flow_pool(flow_id)
            elif scope == "conversation":
                pool = await pool_manager.get_conversation_pool(conversation_id)
                if not pool:
                    # 兜底：如果conversation pool不存在，自动创建
                    if not flow_id:
                        flow_id = await cls._get_flow_id_for_conversation(conversation_id)
                    logger.info(f"自动创建conversation scope的conversation pool: {conversation_id}, flow_id={flow_id}")
                    pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
            else:
                return False, f"不支持的scope类型: {scope}"
            
            if not pool:
                return False, f"无法获取变量池，scope: {scope}"
            
            # 获取变量
            variable = await pool.get_variable(var_name)
            if variable is None:
                logger.error(f"变量 {var_name} 不存在")
                return False, f"变量 {var_name} 不存在"
            
            logger.info(f"找到变量: {var_name}, 类型: {variable.metadata.var_type}")
            
            # 检查变量类型
            if variable.metadata.var_type not in [VariableType.FILE, VariableType.ARRAY_FILE]:
                return False, f"变量 {var_name} 不是文件类型"
            
            # 获取变量配置
            var_config = variable.value
            if not isinstance(var_config, dict):
                logger.error(f"变量 {var_name} 配置格式不正确: {type(var_config)}, 值: {var_config}")
                return False, f"变量 {var_name} 配置格式不正确"
            
            logger.info(f"变量配置: {var_config}")
            
            # 1. 检查文件数量限制
            max_files = var_config.get("max_files", 1 if variable.metadata.var_type == VariableType.FILE else 10)
            if len(documents) > max_files:
                return False, f"文件数量超过限制：最多允许 {max_files} 个文件，实际上传 {len(documents)} 个"
            
            # 2. 检查文件大小限制
            max_file_size = var_config.get("max_file_size", 10 * 1024 * 1024)  # 默认10MB
            for doc in documents:
                if doc.size and doc.size > max_file_size:
                    max_size_mb = max_file_size / (1024 * 1024)
                    return False, f"文件大小超过限制：{doc.filename} 大小为 {doc.size / (1024 * 1024):.1f}MB，最大允许 {max_size_mb:.1f}MB"
            
            # 3. 检查文件类型限制
            supported_types = var_config.get("supported_types", [])
            if supported_types:
                for doc in documents:
                    if doc.filename:
                        file_ext = "." + doc.filename.split(".")[-1].lower() if "." in doc.filename else ""
                        if file_ext not in supported_types:
                            return False, f"文件类型不支持：{doc.filename}，支持的类型：{supported_types}"
            
            # 4. 检查上传方式限制（当前只支持文件流上传）
            upload_methods = var_config.get("upload_methods", ["manual"])
            if "manual" not in upload_methods:
                return False, f"当前上传方式不支持，支持的上传方式：{upload_methods}"
            
            logger.info(f"文件上传验证通过: {var_name}")
            return True, "验证通过"
            
        except Exception as e:
            logger.exception(f"文件上传验证失败: {e}")
            return False, f"验证过程发生错误: {str(e)}"

    @classmethod
    async def storage_docs(cls, user_sub: str, conversation_id: str, documents: list[UploadFile], scope: str = "system", var_name: Optional[str] = None, var_type: Optional[str] = None) -> list[Document]:
        """存储多个文件 - 支持system和conversation scope
        
        🔑 优化说明：支持前端两阶段处理逻辑
        - 前端第一阶段：已通过updateVariable清空file_id/file_ids
        - 这里：上传文件到MinIO/MongoDB，然后更新变量池的file_id/file_ids
        """
        uploaded_files = []

        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        conversation_collection = mongo.get_collection("conversation")
        
        # 🔑 第一步：上传文件到MinIO和MongoDB
        for document in documents:
            if document.filename is None or document.size is None:
                logger.warning(f"跳过无效文件: filename={document.filename}, size={document.size}")
                continue

            file_id = str(uuid.uuid4())
            try:
                mime = await asyncer.asyncify(cls._storage_single_doc_minio)(file_id, document)
                logger.info(f"文件上传到MinIO成功: {file_id}, filename={document.filename}")
            except Exception as e:
                logger.exception(f"[DocumentManager] 上传文件到MinIO失败: filename={document.filename}, error={e}")
                continue

            # 保存到MongoDB
            doc_info = Document(
                _id=file_id,
                user_sub=user_sub,
                name=document.filename,
                type=mime,
                size=document.size / 1024.0,
                conversation_id=conversation_id,
            )
            try:
                await doc_collection.insert_one(doc_info.model_dump(by_alias=True))
                await conversation_collection.update_one(
                    {"_id": conversation_id},
                    {
                        "$push": {"unused_docs": file_id},
                    },
                )
                logger.info(f"文件元数据保存到MongoDB成功: {file_id}")
            except Exception as e:
                logger.exception(f"[DocumentManager] 保存文件元数据到MongoDB失败: file_id={file_id}, error={e}")
                # 尝试清理MinIO中的文件
                try:
                    from apps.common.minio import MinioClient
                    MinioClient.remove_object("document", file_id)
                    logger.info(f"已清理MinIO中的文件: {file_id}")
                except Exception:
                    logger.warning(f"清理MinIO文件失败: {file_id}")
                continue

            # 添加到成功上传列表
            uploaded_files.append(doc_info)

        # 🔑 第二步：更新变量池中的file_id/file_ids
        if uploaded_files:
            try:
                logger.info(f"开始更新变量池: scope={scope}, var_name={var_name}, uploaded_count={len(uploaded_files)}")
                await cls._store_files_in_variable_pool(user_sub, conversation_id, uploaded_files, scope, var_name, var_type)
                logger.info(f"✅ 变量池更新成功: {var_name}")
            except Exception as e:
                logger.exception(f"❌ [DocumentManager] 存储文件变量到变量池失败: var_name={var_name}, error={e}")
                
                # 🔑 重要：变量池更新失败时，需要清理已上传的文件
                logger.warning(f"开始清理已上传的文件，数量: {len(uploaded_files)}")
                cleanup_errors = []
                
                # 清理MongoDB记录
                for doc in uploaded_files:
                    try:
                        await doc_collection.delete_one({"_id": doc.id})
                        await conversation_collection.update_one(
                            {"_id": conversation_id},
                            {"$pull": {"unused_docs": doc.id}}
                        )
                    except Exception as cleanup_error:
                        cleanup_errors.append(f"MongoDB清理失败 {doc.id}: {cleanup_error}")
                
                # 清理MinIO文件
                for doc in uploaded_files:
                    try:
                        from apps.common.minio import MinioClient
                        MinioClient.remove_object("document", doc.id)
                    except Exception as cleanup_error:
                        cleanup_errors.append(f"MinIO清理失败 {doc.id}: {cleanup_error}")
                
                if cleanup_errors:
                    logger.warning(f"文件清理过程中出现错误: {cleanup_errors}")
                
                # 重新抛出原始异常
                raise e
        elif scope == "conversation":
            # 🔑 重要：conversation scope但没有上传任何文件时，也需要确保变量存在
            logger.warning(f"conversation scope但没有成功上传任何文件: var_name={var_name}")

        logger.info(f"文件存储完成: uploaded_count={len(uploaded_files)}, scope={scope}")
        return uploaded_files

    @classmethod
    async def storage_docs_user(cls, user_sub: str, documents: list[UploadFile], var_name: str, var_type: str) -> list[Document]:
        """存储用户scope文件"""
        uploaded_files = []

        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        for document in documents:
            if document.filename is None or document.size is None:
                continue

            file_id = str(uuid.uuid4())
            try:
                mime = await asyncer.asyncify(cls._storage_single_doc_minio)(file_id, document)
            except Exception:
                logger.exception("[DocumentManager] 上传文件失败")
                continue

            # 保存到MongoDB（用户文件不关联conversation）
            doc_info = Document(
                _id=file_id,
                user_sub=user_sub,
                name=document.filename,
                type=mime,
                size=document.size / 1024.0,
                conversation_id="",  # 用户文件不关联conversation
            )
            await doc_collection.insert_one(doc_info.model_dump(by_alias=True))

            # 准备返回值
            uploaded_files.append(doc_info)

        # 在用户变量池中存储文件变量
        if uploaded_files:
            try:
                await cls._store_user_files_in_variable_pool(user_sub, uploaded_files, var_name, var_type)
            except Exception:
                logger.exception("[DocumentManager] 存储用户文件变量到变量池失败")

        return uploaded_files

    @classmethod
    async def storage_docs_env(cls, user_sub: str, flow_id: str, documents: list[UploadFile]) -> list[Document]:
        """存储环境scope文件"""
        uploaded_files = []

        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        for document in documents:
            if document.filename is None or document.size is None:
                continue

            file_id = str(uuid.uuid4())
            try:
                mime = await asyncer.asyncify(cls._storage_single_doc_minio)(file_id, document)
            except Exception:
                logger.exception("[DocumentManager] 上传文件失败")
                continue

            # 保存到MongoDB（环境文件关联flow而不是conversation）
            doc_info = Document(
                _id=file_id,
                user_sub=user_sub,
                name=document.filename,
                type=mime,
                size=document.size / 1024.0,
                conversation_id=flow_id,  # 环境文件用flow_id标识
            )
            await doc_collection.insert_one(doc_info.model_dump(by_alias=True))

            # 准备返回值
            uploaded_files.append(doc_info)

        # 在环境变量池中存储文件变量
        if uploaded_files:
            try:
                await cls._store_env_files_in_variable_pool(user_sub, flow_id, uploaded_files)
            except Exception:
                logger.exception("[DocumentManager] 存储环境文件变量到变量池失败")

        return uploaded_files

    @classmethod
    async def storage_files_for_variable(cls, user_sub: str, files: list[UploadFile], conversation_id: Optional[str] = None, flow_id: Optional[str] = None) -> list[Document]:
        """为变量系统存储文件 - 不包含RAG处理和变量池存储"""
        uploaded_files = []

        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        
        for document in files:
            if document.filename is None or document.size is None:
                continue

            file_id = str(uuid.uuid4())
            try:
                mime = await asyncer.asyncify(cls._storage_single_doc_minio)(file_id, document)
            except Exception:
                logger.exception("[DocumentManager] 上传文件失败")
                continue

            # 保存到MongoDB
            doc_info = Document(
                _id=file_id,
                user_sub=user_sub,
                name=document.filename,
                type=mime,
                size=document.size / 1024.0,
                conversation_id=conversation_id or "",
            )
            await doc_collection.insert_one(doc_info.model_dump(by_alias=True))

            # 如果有关联的conversation，更新conversation的unused_docs
            if conversation_id:
                conversation_collection = mongo.get_collection("conversation")
                await conversation_collection.update_one(
                    {"_id": conversation_id},
                    {
                        "$push": {"unused_docs": file_id},
                    },
                )

            # 准备返回值
            uploaded_files.append(doc_info)

        return uploaded_files

    @classmethod
    async def _store_files_in_variable_pool(cls, user_sub: str, conversation_id: str, uploaded_files: list[Document], scope: str, var_name: Optional[str] = None, var_type: Optional[str] = None):
        """将文件存储到变量池中 - 支持system和conversation scope
        
        🔑 优化说明：支持前端两阶段处理逻辑
        - 前端第一阶段已清空file_id，这里只需要安全更新file_id
        - 避免与前端的变量更新逻辑冲突
        """
        pool_manager = await get_pool_manager()
        
        # 根据scope确定变量池和is_system值
        if scope == "system":
            pool = await pool_manager.get_conversation_pool(conversation_id)
            if not pool:
                flow_id = await cls._get_flow_id_for_conversation(conversation_id)
                pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
            is_system = True
        elif scope == "conversation":
            pool = await pool_manager.get_conversation_pool(conversation_id)
            if not pool:
                flow_id = await cls._get_flow_id_for_conversation(conversation_id)
                pool = await pool_manager.create_conversation_pool(conversation_id, flow_id)
            is_system = False
        else:
            logger.warning(f"不支持的scope类型: {scope}")
            return

        if not pool:
            logger.warning(f"无法获取变量池，scope: {scope}")
            return

        # 确定变量名称、类型和值
        if scope == "system":
            # 对于system scope，使用固定变量名system.files
            final_var_name = "system.files"
            final_var_type = VariableType.ARRAY_FILE  # 系统文件变量统一使用数组类型
        else:  # conversation scope
            # 对于conversation scope，使用传入的var_name和var_type
            final_var_name = var_name
            final_var_type = VariableType(var_type)  # 转换为VariableType枚举

        # 检查变量是否已存在
        existing_variable = await pool.get_variable(final_var_name)
        if existing_variable is not None:
            # 🔑 重要优化：安全更新现有变量，保持原有配置
            if existing_variable.metadata.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                # 🔧 新增：数据验证和自动修复机制
                from apps.scheduler.variable.file_utils import FileVariableHelper
                
                # 获取现有变量的配置
                current_value = existing_variable.value
                if isinstance(current_value, dict):
                    # 验证和标准化现有数据
                    var_type_str = existing_variable.metadata.var_type.value
                    is_valid, error_msg = FileVariableHelper.validate_file_variable_consistency(current_value, var_type_str)
                    
                    if not is_valid:
                        logger.warning(f"检测到变量 {final_var_name} 数据不一致: {error_msg}，将自动修复")
                        # 自动标准化数据
                        current_value = FileVariableHelper.normalize_file_variable(current_value, var_type_str)
                        logger.info(f"已自动修复变量 {final_var_name} 的数据格式")
                    
                    # 🔑 关键：保持所有现有配置，只更新file_id
                    updated_value = current_value.copy()  # 深拷贝保持原有配置
                    
                    if existing_variable.metadata.var_type == VariableType.FILE:
                        # 单文件：设置file_id和filename
                        if uploaded_files:
                            updated_value["file_id"] = uploaded_files[0].id
                            updated_value["filename"] = uploaded_files[0].name  # 新增：保存原始文件名
                            logger.info(f"更新单文件变量 {final_var_name}: file_id={updated_value['file_id']}, filename={updated_value['filename']}")
                        else:
                            updated_value["file_id"] = ""
                            updated_value.pop("filename", None)  # 清空文件名
                            logger.info(f"清空单文件变量 {final_var_name}")
                    else:  # ARRAY_FILE
                        # 文件数组：设置file_ids和files信息，确保数据一致性
                        file_ids_list = [doc.id for doc in uploaded_files]
                        files_list = [  # 新增：保存文件详细信息
                            {"file_id": doc.id, "filename": doc.name} 
                            for doc in uploaded_files
                        ]
                        
                        # 🔧 重要：确保file_ids和files数组始终保持同步
                        updated_value["file_ids"] = file_ids_list
                        updated_value["files"] = files_list
                        
                        # 🔧 验证数据一致性
                        if len(file_ids_list) != len(files_list):
                            logger.warning(f"文件数组变量数据不一致: file_ids={len(file_ids_list)}, files={len(files_list)}")
                        
                        logger.info(f"更新文件数组变量 {final_var_name}: file_ids={updated_value['file_ids']}, files={len(updated_value['files'])}个文件")
                    
                    # 🔑 使用原子更新，避免并发冲突
                    try:
                        await pool.update_variable(
                            name=final_var_name,
                            value=updated_value,
                            var_type=existing_variable.metadata.var_type,
                            description=existing_variable.metadata.description
                        )
                        logger.info(f"✅ 成功更新文件变量: {final_var_name}, uploaded_files_count={len(uploaded_files)}")
                    except Exception as e:
                        logger.error(f"❌ 更新文件变量失败: {final_var_name}, error={e}")
                        # 抛出异常，让上层处理文件上传失败的清理工作
                        raise Exception(f"文件变量更新失败: {e}")
                else:
                    logger.warning(f"现有变量 {final_var_name} 的值格式不正确，无法更新: type={type(current_value)}, value={current_value}")
                    raise Exception(f"变量 {final_var_name} 配置格式错误")
            else:
                logger.warning(f"现有变量 {final_var_name} 不是文件类型，无法更新: type={existing_variable.metadata.var_type}")
                raise Exception(f"变量 {final_var_name} 不是文件类型")
        else:
            # 只有system scope允许创建新变量
            if scope == "system":
                # 创建新的system.files变量
                file_ids_list = [doc.id for doc in uploaded_files]
                files_list = [  # 新增：保存文件详细信息
                    {"file_id": doc.id, "filename": doc.name} 
                    for doc in uploaded_files
                ]
                
                final_var_value = {
                    "file_ids": file_ids_list,  # 确保使用相同的数据源
                    "files": files_list,        # 确保使用相同的数据源
                    "supported_types": [],
                    "upload_methods": ["manual"],
                    "max_files": len(uploaded_files),
                    "max_file_size": 10 * 1024 * 1024,  # 10MB
                    "required": False
                }
                
                # 🔧 验证数据一致性
                if len(file_ids_list) != len(files_list):
                    logger.warning(f"新建system变量数据不一致: file_ids={len(file_ids_list)}, files={len(files_list)}")
                    
                logger.info(f"创建新的system.files变量: file_ids={len(file_ids_list)}个文件, files={len(files_list)}个详细信息")
                
                await pool.add_variable(
                    name=final_var_name,
                    var_type=final_var_type,
                    value=final_var_value,
                    description=f"上传的文件，scope: {scope}",
                    created_by=user_sub,
                    is_system=is_system
                )
                logger.info(f"已创建新的system.files变量")
            else:
                # 🔑 重要：conversation变量必须预先存在（前端第一阶段已创建）
                logger.error(f"conversation变量 {final_var_name} 不存在，这可能表示前端第一阶段处理失败")
                raise Exception(f"变量 {final_var_name} 不存在，无法上传文件")

        logger.info(f"✅ 已将文件存储到变量池，变量名: {final_var_name}, 类型: {final_var_type}, scope: {scope}")

    @classmethod
    async def _store_user_files_in_variable_pool(cls, user_sub: str, uploaded_files: list[Document], var_name: str, var_type: str):
        """将用户scope文件存储到变量池中"""
        pool_manager = await get_pool_manager()
        pool = await pool_manager.get_user_pool(user_sub)

        if not pool:
            logger.warning(f"无法获取用户变量池，user_sub: {user_sub}")
            return

        # 检查变量是否已存在
        existing_variable = await pool.get_variable(var_name)
        if existing_variable:
            # 更新现有变量
            if existing_variable.metadata.var_type in [VariableType.FILE, VariableType.ARRAY_FILE]:
                # 获取现有变量的配置
                current_value = existing_variable.value
                if isinstance(current_value, dict):
                    # 更新文件ID
                    if existing_variable.metadata.var_type == VariableType.FILE:
                        current_value["file_id"] = uploaded_files[0].id if uploaded_files else ""
                    else:  # ARRAY_FILE
                        current_value["file_ids"] = [doc.id for doc in uploaded_files]
                    
                    # 更新变量
                    await pool.update_variable(
                        name=var_name,
                        value=current_value,
                        var_type=existing_variable.metadata.var_type,
                        description=existing_variable.metadata.description
                    )
                    logger.info(f"已更新用户文件变量: {var_name}")
                else:
                    logger.warning(f"现有变量 {var_name} 的值格式不正确，无法更新")
            else:
                logger.warning(f"现有变量 {var_name} 不是文件类型，无法更新")
        else:
            # 创建新变量（只允许system scope创建新变量，这里应该不会执行）
            logger.warning(f"用户变量 {var_name} 不存在，无法创建新变量")
            return

        logger.info(f"已将用户文件存储到变量池，变量名: {var_name}, 类型: {var_type}, user_sub: {user_sub}")

    @classmethod
    async def _store_env_files_in_variable_pool(cls, user_sub: str, flow_id: str, uploaded_files: list[Document]):
        """将环境scope文件存储到变量池中"""
        pool_manager = await get_pool_manager()
        pool = await pool_manager.get_flow_pool(flow_id)

        if not pool:
            logger.warning(f"无法获取环境变量池，flow_id: {flow_id}")
            return

        # 检查env.files变量是否已存在
        var_name = "env.files"
        existing_variable = await pool.get_variable(var_name)
        if existing_variable:
            # 更新现有变量
            if existing_variable.metadata.var_type == VariableType.ARRAY_FILE:
                # 获取现有变量的配置
                current_value = existing_variable.value
                if isinstance(current_value, dict):
                    # 更新文件ID列表
                    current_value["file_ids"] = [doc.id for doc in uploaded_files]
                    
                    # 更新变量
                    await pool.update_variable(
                        name=var_name,
                        value=current_value,
                        var_type=existing_variable.metadata.var_type,
                        description=existing_variable.metadata.description
                    )
                    logger.info(f"已更新环境文件变量: {var_name}")
                else:
                    logger.warning(f"现有变量 {var_name} 的值格式不正确，无法更新")
            else:
                logger.warning(f"现有变量 {var_name} 不是文件类型，无法更新")
        else:
            # 创建新变量（只允许system scope创建新变量，这里应该不会执行）
            logger.warning(f"环境变量 {var_name} 不存在，无法创建新变量")
            return

        logger.info(f"已将环境文件存储到变量池，变量名: {var_name}, user_sub: {user_sub}, flow_id: {flow_id}")

    @classmethod
    async def _get_flow_id_for_conversation(cls, conversation_id: str) -> str:
        """获取对话对应的flow_id"""
        try:
            mongo = MongoDB()
            conversation_collection = mongo.get_collection("conversation")
            conversation = await conversation_collection.find_one({"_id": conversation_id})
            
            if conversation and conversation.get("app_id"):
                # 使用app_id作为flow_id
                return conversation["app_id"]
            else:
                # 如果没有app_id，使用默认值
                return "default_flow"
        except Exception:
            logger.exception(f"获取conversation {conversation_id} 的flow_id失败")
            return "default_flow"

    @classmethod
    async def get_unused_docs(cls, user_sub: str, conversation_id: str) -> list[Document]:
        """获取Conversation中未使用的文件"""
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
        doc_collection = mongo.get_collection("document")

        conv = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not conv:
            logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
            return []

        docs_ids = conv.get("unused_docs", [])
        return [Document(**doc) async for doc in doc_collection.find({"_id": {"$in": docs_ids}})]

    @classmethod
    async def get_used_docs_by_record_group(
            cls, user_sub: str, record_group_id: str, type: str | None = None) -> list[RecordDocument]:
        """获取RecordGroup关联的文件"""
        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")
        document_collection = mongo.get_collection("document")
        if type not in ["question", "answer", None]:
            raise ValueError("type must be 'question', 'answer' or None")
        record_group = await record_group_collection.find_one({"_id": record_group_id, "user_sub": user_sub})
        if not record_group:
            logger.info("[DocumentManager] 记录组不存在: %s", record_group_id)
            return []

        docs = RecordGroup.model_validate(record_group).docs
        for doc in docs:
            if doc.associated == "question":
                doc_info = await document_collection.find_one({"_id": doc.id, "user_sub": user_sub})
                doc_info = Document.model_validate(doc_info) if doc_info else None
                if doc_info:
                    doc.name = doc_info.name
                    doc.extension = doc_info.type
                    doc.size = doc_info.size
        return [
            RecordDocument(
                _id=doc.id,
                order=doc.order,
                author=doc.author,
                abstract=doc.abstract,
                name=doc.name,
                type=doc.extension,
                size=doc.size,
                conversation_id=record_group.get("conversation_id", ""),
                associated=doc.associated,
                created_at=doc.created_at or round(datetime.now(tz=UTC).timestamp(), 3)
            )
            for doc in docs if type is None or doc.associated == type
        ]

    @classmethod
    async def get_used_docs(
            cls, user_sub: str, conversation_id: str, record_num: int | None = 10, type: str | None = None) -> list[Document]:
        """获取最后n次问答所用到的文件"""
        mongo = MongoDB()
        docs_collection = mongo.get_collection("document")
        record_group_collection = mongo.get_collection("record_group")
        if type not in ["question", "answer", None]:
            raise ValueError("type must be 'question', 'answer' or None")
        if record_num:
            record_groups = (
                record_group_collection.find({"conversation_id": conversation_id, "user_sub": user_sub})
                .sort("created_at", -1)
                .limit(record_num)
            )
        else:
            record_groups = record_group_collection.find(
                {"conversation_id": conversation_id, "user_sub": user_sub},
            ).sort("created_at", -1)

        docs = []
        async for current_record_group in record_groups:
            for doc in RecordGroup.model_validate(current_record_group).docs:
                if type is None or doc.associated == type:
                    docs.append(doc.id)
        # 文件ID去重
        docs = list(set(docs))
        # 返回文件详细信息
        return [Document.model_validate(doc) async for doc in docs_collection.find({"_id": {"$in": docs}})]

    @classmethod
    def _remove_doc_from_minio(cls, doc_id: str) -> None:
        """从MinIO中删除文件"""
        MinioClient.delete_file("document", doc_id)

    @classmethod
    async def delete_document(cls, user_sub: str, document_list: list[str]) -> bool:
        """从未使用文件列表中删除一个文件"""
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        conv_collection = mongo.get_collection("conversation")
        try:
            async with mongo.get_session() as session, await session.start_transaction():
                for doc in document_list:
                    doc_info = await doc_collection.find_one_and_delete(
                        {"_id": doc, "user_sub": user_sub}, session=session,
                    )
                    # 删除Document表内文件
                    if not doc_info:
                        logger.error("[DocumentManager] 文件不存在: %s", doc)
                        continue

                    # 删除MinIO内文件
                    await asyncer.asyncify(cls._remove_doc_from_minio)(doc)

                    # 删除Conversation内文件
                    conv = await conv_collection.find_one({"_id": doc_info["conversation_id"]}, session=session)
                    if conv:
                        await conv_collection.update_one(
                            {"_id": conv["_id"]},
                            {
                                "$pull": {"unused_docs": doc},
                            },
                            session=session,
                        )
                await session.commit_transaction()
                return True
        except Exception:
            logger.exception("[DocumentManager] 删除文件失败")
            return False

    @classmethod
    async def delete_document_by_conversation_id(cls, user_sub: str, conversation_id: str) -> list[str]:
        """通过ConversationID删除文件"""
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        doc_ids = []

        async with mongo.get_session() as session, await session.start_transaction():
            async for doc in doc_collection.find(
                {"user_sub": user_sub, "conversation_id": conversation_id}, session=session,
            ):
                doc_ids.append(doc["_id"])
                await asyncer.asyncify(cls._remove_doc_from_minio)(doc["_id"])
                await doc_collection.delete_one({"_id": doc["_id"]}, session=session)
            await session.commit_transaction()

        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        if not session_id:
            logger.error("[DocumentManager] Session不存在: %s", user_sub)
            return []
        await KnowledgeBaseService.delete_doc_from_rag(session_id, doc_ids)
        return doc_ids

    @classmethod
    async def get_doc_count(cls, user_sub: str, conversation_id: str) -> int:
        """获取对话文件数量"""
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        return await doc_collection.count_documents({"user_sub": user_sub, "conversation_id": conversation_id})

    @classmethod
    async def change_doc_status(cls, user_sub: str, conversation_id: str, record_group_id: str) -> None:
        """文件状态由unused改为used"""
        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")
        conversation_collection = mongo.get_collection("conversation")

        # 查找Conversation中的unused_docs
        conversation = await conversation_collection.find_one({"user_sub": user_sub, "_id": conversation_id})
        if not conversation:
            logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
            return

        # 把unused_docs加入RecordGroup中，并与问题关联
        docs_id = Conversation.model_validate(conversation).unused_docs
        for doc in docs_id:
            doc_info = RecordGroupDocument(_id=doc, associated="question")
            await record_group_collection.update_one(
                {"_id": record_group_id, "user_sub": user_sub},
                {"$push": {"docs": doc_info.model_dump(by_alias=True)}},
            )

        # 把unused_docs从Conversation中删除
        await conversation_collection.update_one({"_id": conversation_id}, {"$set": {"unused_docs": []}})

    @classmethod
    async def save_answer_doc(cls, user_sub: str, record_group_id: str, doc_infos: list[RecordDocument]) -> None:
        """保存与答案关联的文件"""
        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")
        for doc_info in doc_infos:
            await record_group_collection.update_one(
                {"_id": record_group_id, "user_sub": user_sub},
                {"$push": {"docs": doc_info.model_dump(by_alias=True)}},
            )
