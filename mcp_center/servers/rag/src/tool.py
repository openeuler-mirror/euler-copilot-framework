import os
import sys
import uuid
import shutil
import logging
import asyncio
import json
from typing import Optional, Dict, Any, List

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from base.manager.database_manager import Database
from base.manager.document_manager import DocumentManager, import_document as _import_document, update_document as _update_document
from base.config import get_default_top_k
from base.models import KnowledgeBase
from base.search.weighted_keyword_and_vector_search import weighted_keyword_and_vector_search

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

_db_instance: Optional[Database] = None
_db_path = os.path.join(current_dir, "database", "kb.db")
_current_kb_id: Optional[str] = None
_state_file = os.path.join(current_dir, "database", "state.json")


def _load_state() -> None:
    """从状态文件加载当前知识库ID（用于在不同进程间共享选择状态）"""
    global _current_kb_id
    try:
        if os.path.exists(_state_file):
            with open(_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _current_kb_id = data.get("current_kb_id")
    except Exception as e:
        logger.warning(f"[state] 加载当前知识库状态失败: {e}")


def _save_state() -> None:
    """将当前知识库ID写入状态文件"""
    try:
        state_dir = os.path.dirname(_state_file)
        if not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)
        with open(_state_file, "w", encoding="utf-8") as f:
            json.dump({"current_kb_id": _current_kb_id}, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[state] 保存当前知识库状态失败: {e}")


# 模块导入时尝试加载之前保存的当前知识库状态
_load_state()


def _get_db() -> Database:
    """获取数据库实例（固定使用kb.db）"""
    global _db_instance
    if _db_instance is None:
        db_dir = os.path.dirname(_db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        _db_instance = Database(_db_path)
    return _db_instance


def _ensure_active_kb(result: Dict[str, Any]) -> Optional[str]:
    """确保已选择知识库"""
    if not _current_kb_id:
        result["message"] = "请先选择知识库"
        return None
    return _current_kb_id


def create_knowledge_base(
    kb_name: str,
    chunk_size: int,
    embedding_model: Optional[str] = None,
    embedding_endpoint: Optional[str] = None,
    embedding_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    新增知识库
    
    :param kb_name: 知识库名称
    :param chunk_size: chunk 大小（token 数）
    :param embedding_model: 向量化模型名称（可选）
    :param embedding_endpoint: 向量化服务端点（可选）
    :param embedding_api_key: 向量化服务 API Key（可选）
    :return: 创建结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        db = _get_db()
        session = db.get_session()
        try:
            # 检查知识库名称是否已存在
            existing_kb = db.get_knowledge_base(kb_name)
            if existing_kb:
                result["message"] = f"知识库 '{kb_name}' 已存在"
                return result
            
            kb_id = str(uuid.uuid4())
            if db.add_knowledge_base(kb_id, kb_name, chunk_size, 
                                    embedding_model, embedding_endpoint, embedding_api_key):
                result["success"] = True
                result["message"] = f"成功创建知识库: {kb_name}"
                result["data"] = {
                    "kb_id": kb_id,
                    "kb_name": kb_name,
                    "chunk_size": chunk_size
                }
            else:
                result["message"] = "创建知识库失败"
        finally:
            session.close()
    except Exception as e:
        logger.exception(f"[create_knowledge_base] 创建知识库失败: {e}")
        result["message"] = "创建知识库失败"
    
    return result


def delete_knowledge_base(kb_name: str) -> Dict[str, Any]:
    """
    删除知识库
    
    :param kb_name: 知识库名称
    :return: 删除结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        db = _get_db()
        kb = db.get_knowledge_base(kb_name)
        if not kb:
            result["message"] = f"知识库 '{kb_name}' 不存在"
            return result
        
        # 检查是否是当前使用的知识库
        global _current_kb_id
        if _current_kb_id == kb.id:
            result["message"] = "不能删除当前正在使用的知识库"
            return result
        
        if db.delete_knowledge_base(kb.id):
            result["success"] = True
            result["message"] = f"成功删除知识库: {kb_name}"
            result["data"] = {"kb_name": kb_name}
        else:
            result["message"] = "删除知识库失败"
    except Exception as e:
        logger.exception(f"[delete_knowledge_base] 删除知识库失败: {e}")
        result["message"] = "删除知识库失败"
    
    return result


def list_knowledge_bases() -> Dict[str, Any]:
    """
    查看知识库列表
    
    :return: 知识库列表
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        db = _get_db()
        kbs = db.list_knowledge_bases()
        
        knowledge_bases = []
        global _current_kb_id
        for kb in kbs:
            knowledge_bases.append({
                "id": kb.id,
                "name": kb.name,
                "chunk_size": kb.chunk_size,
                "embedding_model": kb.embedding_model,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
                "is_current": _current_kb_id == kb.id
            })
        
        result["success"] = True
        result["message"] = f"找到 {len(knowledge_bases)} 个知识库"
        result["data"] = {
            "knowledge_bases": knowledge_bases,
            "count": len(knowledge_bases),
            "current_kb_id": _current_kb_id
        }
    except Exception as e:
        logger.exception(f"[list_knowledge_bases] 获取知识库列表失败: {e}")
        result["message"] = "获取知识库列表失败"
    
    return result


def select_knowledge_base(kb_name: str) -> Dict[str, Any]:
    """
    选择知识库
    
    :param kb_name: 知识库名称
    :return: 选择结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        db = _get_db()
        kb = db.get_knowledge_base(kb_name)
        if not kb:
            result["message"] = f"知识库 '{kb_name}' 不存在"
            return result
        
        global _current_kb_id
        _current_kb_id = kb.id
        _save_state()
        
        session = db.get_session()
        try:
            manager = DocumentManager(session)
            docs = manager.list_documents_by_kb(kb.id)
            doc_count = len(docs)
        finally:
            session.close()
        
        result["success"] = True
        result["message"] = f"成功选择知识库，共 {doc_count} 个文档"
        result["data"] = {
            "kb_id": kb.id,
            "kb_name": kb.name,
            "document_count": doc_count
        }
    except Exception as e:
        logger.exception(f"[select_knowledge_base] 选择知识库失败: {e}")
        result["message"] = "选择知识库失败"
    
    return result


async def import_document(file_paths: List[str], chunk_size: Optional[int] = None) -> Dict[str, Any]:
    """
    上传文档到当前知识库（异步，支持多文件并发导入）
    
    :param file_paths: 文件路径列表（绝对路径），支持1~n个文件
    :param chunk_size: chunk 大小（token 数，可选，默认使用知识库的chunk_size）
    :return: 导入结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        kb_id = _ensure_active_kb(result)
        if not kb_id:
            return result
        
        if not file_paths:
            result["message"] = "文件路径列表为空"
            return result
        
        # 验证文件路径是否存在
        invalid_paths = [path for path in file_paths if not os.path.exists(path)]
        if invalid_paths:
            result["message"] = f"以下文件路径不存在: {', '.join(invalid_paths)}"
            return result
        
        db = _get_db()
        # 先获取知识库信息
        session = db.get_session()
        try:
            kb = session.query(KnowledgeBase).filter_by(id=kb_id).first()
            if not kb:
                result["message"] = "知识库不存在"
                return result
            
            if chunk_size is None:
                chunk_size = kb.chunk_size
        finally:
            session.close()
        
        # 并发处理多个文件，每个文件使用独立的 session
        async def import_single_file(file_path: str):
            """为单个文件创建独立的 session 并导入"""
            file_session = db.get_session()
            try:
                return await _import_document(file_session, kb_id, file_path, chunk_size)
            finally:
                file_session.close()
        
        tasks = [
            import_single_file(file_path)
            for file_path in file_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = 0
        failed_count = 0
        success_files = []
        failed_files = []
        
        for i, res in enumerate(results):
            file_path = file_paths[i]
            if isinstance(res, Exception):
                failed_count += 1
                failed_files.append({
                    "file_path": file_path,
                    "error": str(res)
                })
                logger.exception(f"[import_document] 导入文件失败: {file_path}, 错误: {res}")
            else:
                success, message, data = res
                if success:
                    success_count += 1
                    success_files.append({
                        "file_path": file_path,
                        "doc_name": data.get("doc_name") if data else os.path.basename(file_path),
                        "chunk_count": data.get("chunk_count", 0) if data else 0
                    })
                else:
                    failed_count += 1
                    failed_files.append({
                        "file_path": file_path,
                        "error": message
                    })
        
        result["success"] = success_count > 0
        result["message"] = f"成功导入 {success_count} 个文档，失败 {failed_count} 个"
        result["data"] = {
            "total": len(file_paths),
            "success_count": success_count,
            "failed_count": failed_count,
            "success_files": success_files,
            "failed_files": failed_files
        }
    except Exception as e:
        logger.exception(f"[import_document] 导入文档失败: {e}")
        result["message"] = f"导入文档失败: {str(e)}"
    
    return result


async def search(query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    """
    在当前知识库中查询（异步）
    
    :param query: 查询文本
    :param top_k: 返回数量（可选，默认从配置读取）
    :return: 检索结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    if top_k is None:
        top_k = get_default_top_k()
    
    kb_id = _ensure_active_kb(result)
    if not kb_id:
        return result
    
    weight_keyword = 0.3
    weight_vector = 0.7
    
    try:
        db = _get_db()
        session = db.get_session()
        try:
            # 获取当前知识库的所有文档ID
            manager = DocumentManager(session)
            docs = manager.list_documents_by_kb(kb_id)
            doc_ids = [doc.id for doc in docs]
            
            if not doc_ids:
                result["message"] = "当前知识库中没有文档"
                result["data"] = {"chunks": []}
                return result
            
            conn = session.connection()
            chunks = await weighted_keyword_and_vector_search(
                conn, query, top_k, weight_keyword, weight_vector, doc_ids
            )
        finally:
            session.close()
        
        if not chunks:
            result["message"] = "未找到相关结果"
            result["data"] = {"chunks": []}
            return result
        
        result["success"] = True
        result["message"] = f"找到 {len(chunks)} 个相关结果"
        result["data"] = {
            "chunks": chunks,
            "count": len(chunks)
        }
    except Exception as e:
        logger.exception(f"[search] 搜索失败: {e}")
        result["message"] = "搜索失败"
    
    return result


def list_documents() -> Dict[str, Any]:
    """
    查看当前知识库下的文档列表
    
    :return: 文档列表
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        kb_id = _ensure_active_kb(result)
        if not kb_id:
            return result
        
        db = _get_db()
        session = db.get_session()
        try:
            manager = DocumentManager(session)
            docs = manager.list_documents_by_kb(kb_id)
        finally:
            session.close()
        
        documents = []
        for doc in docs:
            documents.append({
                "id": doc.id,
                "name": doc.name,
                "file_path": doc.file_path,
                "file_type": doc.file_type,
                "chunk_size": doc.chunk_size,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
            })
        
        result["success"] = True
        result["message"] = f"找到 {len(documents)} 个文档"
        result["data"] = {
            "documents": documents,
            "count": len(documents)
        }
    except Exception as e:
        logger.exception(f"[list_documents] 获取文档列表失败: {e}")
        result["message"] = "获取文档列表失败"
    
    return result


def delete_document(doc_name: str) -> Dict[str, Any]:
    """
    删除当前知识库下的文档
    
    :param doc_name: 文档名称
    :return: 删除结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        kb_id = _ensure_active_kb(result)
        if not kb_id:
            return result
        
        db = _get_db()
        session = db.get_session()
        try:
            manager = DocumentManager(session)
            if manager.delete_document(kb_id, doc_name):
                result["success"] = True
                result["message"] = f"成功删除文档: {doc_name}"
                result["data"] = {"doc_name": doc_name}
            else:
                result["message"] = f"文档 '{doc_name}' 不存在或删除失败"
        finally:
            session.close()
    except Exception as e:
        logger.exception(f"[delete_document] 删除文档失败: {e}")
        result["message"] = "删除文档失败"
    
    return result


async def update_document(doc_name: str, chunk_size: int) -> Dict[str, Any]:
    """
    修改文档的chunk_size并重新解析（异步）
    
    :param doc_name: 文档名称
    :param chunk_size: 新的chunk大小
    :return: 修改结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        kb_id = _ensure_active_kb(result)
        if not kb_id:
            return result
        
        db = _get_db()
        session = db.get_session()
        try:
            success, message, data = await _update_document(session, kb_id, doc_name, chunk_size)
            result["success"] = success
            result["message"] = message
            result["data"] = data or {}
        finally:
            session.close()
    except Exception as e:
        logger.exception(f"[update_document] 修改文档失败: {e}")
        result["message"] = "修改文档失败"
    
    return result


def export_database(export_path: str) -> Dict[str, Any]:
    """
    导出整个kb.db数据库文件
    
    :param export_path: 导出路径（绝对路径）
    :return: 导出结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        if not os.path.exists(_db_path):
            result["message"] = "数据库文件不存在"
            return result
        
        if not export_path:
            result["message"] = "导出路径不能为空"
            return result
        
        # 确保导出路径以 .db 结尾
        if not export_path.endswith(('.db', '.sqlite', '.sqlite3')):
            export_path += '.db'
        
        # 确保目标目录存在
        export_dir = os.path.dirname(export_path)
        if export_dir and not os.path.exists(export_dir):
            os.makedirs(export_dir, exist_ok=True)
        
        shutil.copy2(_db_path, export_path)
        
        result["success"] = True
        result["message"] = f"成功导出数据库到: {export_path}"
        result["data"] = {
            "source_path": _db_path,
            "export_path": export_path
        }
    except Exception as e:
        logger.exception(f"[export_database] 导出数据库失败: {e}")
        result["message"] = f"导出数据库失败: {str(e)}"
    
    return result


def import_database(source_db_path: str) -> Dict[str, Any]:
    """
    导入一个.db数据库文件，将其中的内容合并到kb.db中
    
    :param source_db_path: 源数据库文件路径（绝对路径）
    :return: 导入结果
    """
    result = {
        "success": False,
        "message": "",
        "data": {}
    }
    
    try:
        if not source_db_path:
            result["message"] = "源数据库路径不能为空"
            return result
        
        if not os.path.exists(source_db_path):
            result["message"] = f"源数据库文件不存在: {source_db_path}"
            return result
        
        db = _get_db()
        imported_kb_count, imported_doc_count = db.import_database(source_db_path)
        
        result["success"] = True
        result["message"] = f"成功导入，共 {imported_kb_count} 个知识库，{imported_doc_count} 个文档"
        result["data"] = {
            "source_path": source_db_path,
            "imported_kb_count": imported_kb_count,
            "imported_doc_count": imported_doc_count
        }
    except Exception as e:
        logger.exception(f"[import_database] 导入数据库失败: {e}")
        result["message"] = f"导入数据库失败: {str(e)}"
    
    return result
