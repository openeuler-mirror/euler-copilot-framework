import os
import sys
import asyncio
import json
from typing import Dict, Any

# 添加路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加 mcp_center 目录到路径
mcp_center_dir = os.path.abspath(os.path.join(current_dir, '../../..'))
if mcp_center_dir not in sys.path:
    sys.path.insert(0, mcp_center_dir)

from tool import (
    create_knowledge_base,
    delete_knowledge_base,
    list_knowledge_bases,
    select_knowledge_base,
    import_document,
    search,
    list_documents,
    delete_document,
    update_document,
    export_database,
    import_database
)

def print_result(result: Dict[str, Any]):
    """打印结果"""
    if result.get("success"):
        print(f"✅ {result.get('message', '操作成功')}")
        if result.get("data"):
            print(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        print(f"❌ {result.get('message', '操作失败')}")

def handle_create_kb(args):
    """创建知识库"""
    if not args.kb_name or not args.chunk_size:
        print("❌ 缺少参数：--kb_name 和 --chunk_size 必填")
        return False
    
    result = create_knowledge_base(
        kb_name=args.kb_name,
        chunk_size=args.chunk_size,
        embedding_model=args.embedding_model,
        embedding_endpoint=args.embedding_endpoint,
        embedding_api_key=args.embedding_api_key
    )
    print_result(result)
    return result.get("success", False)

def handle_delete_kb(args):
    """删除知识库"""
    if not args.kb_name:
        print("❌ 缺少参数：--kb_name 必填")
        return False
    
    result = delete_knowledge_base(args.kb_name)
    print_result(result)
    return result.get("success", False)

def handle_list_kb(args):
    """列出知识库"""
    result = list_knowledge_bases()
    print_result(result)
    return result.get("success", False)

def handle_select_kb(args):
    """选择知识库"""
    if not args.kb_name:
        print("❌ 缺少参数：--kb_name 必填")
        return False
    
    result = select_knowledge_base(args.kb_name)
    print_result(result)
    return result.get("success", False)

async def handle_import_doc_async(args):
    """导入文档（异步）"""
    if not args.file_paths:
        print("❌ 缺少参数：--file_paths 必填（文件路径列表）")
        return False
    
    result = await import_document(
        file_paths=args.file_paths,
        chunk_size=args.chunk_size
    )
    print_result(result)
    return result.get("success", False)

def handle_import_doc(args):
    """导入文档（同步包装）"""
    return asyncio.run(handle_import_doc_async(args))

def handle_list_doc(args):
    """列出文档"""
    result = list_documents()
    print_result(result)
    return result.get("success", False)

def handle_delete_doc(args):
    """删除文档"""
    if not args.doc_name:
        print("❌ 缺少参数：--doc_name 必填")
        return False
    
    result = delete_document(args.doc_name)
    print_result(result)
    return result.get("success", False)

async def handle_update_doc_async(args):
    """更新文档（异步）"""
    if not args.doc_name or not args.chunk_size:
        print("❌ 缺少参数：--doc_name 和 --chunk_size 必填")
        return False
    
    result = await update_document(
        doc_name=args.doc_name,
        chunk_size=args.chunk_size
    )
    print_result(result)
    return result.get("success", False)

def handle_update_doc(args):
    """更新文档（同步包装）"""
    return asyncio.run(handle_update_doc_async(args))

async def handle_search_async(args):
    """搜索（异步）"""
    if not args.query:
        print("❌ 缺少参数：--query 必填")
        return False
    
    result = await search(
        query=args.query,
        top_k=args.top_k
    )
    print_result(result)
    return result.get("success", False)

def handle_search(args):
    """搜索（同步包装）"""
    return asyncio.run(handle_search_async(args))

def handle_export_db(args):
    """导出数据库"""
    if not args.export_path:
        print("❌ 缺少参数：--export_path 必填（绝对路径）")
        return False
    
    result = export_database(args.export_path)
    print_result(result)
    return result.get("success", False)

def handle_import_db(args):
    """导入数据库"""
    if not args.source_db_path:
        print("❌ 缺少参数：--source_db_path 必填（绝对路径）")
        return False
    
    result = import_database(args.source_db_path)
    print_result(result)
    return result.get("success", False)

