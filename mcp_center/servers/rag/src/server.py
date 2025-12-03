"""
MCP Server for Copilot-0 Knowledge Base Management
将 copilot-0 项目启动为 MCP 服务
"""
import os
import sys
import json
from typing import Optional, Dict, Any, List
from mcp.server import FastMCP

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 添加 mcp_center 目录到路径（用于导入配置模块）
mcp_center_dir = os.path.abspath(os.path.join(current_dir, '../../..'))
if mcp_center_dir not in sys.path:
    sys.path.insert(0, mcp_center_dir)

# 导入配置加载器
from config.public.base_config_loader import LanguageEnum
from config.private.rag.config_loader import RemoteInfoConfig as RagConfig

# 导入 tool.py 中的所有函数
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

# 加载配置文件
config_path = os.path.join(current_dir, "config.json")
with open(config_path, 'r', encoding='utf-8') as f:
    tool_configs = json.load(f)["tools"]

# 获取语言配置
_config = RagConfig().get_config()
_language = _config.public_config.language

# 辅助函数：根据语言获取工具描述
def get_tool_description(tool_name: str) -> str:
    """根据配置的语言获取工具描述"""
    tool_desc = tool_configs.get(tool_name, {})
    if _language == LanguageEnum.ZH:
        return tool_desc.get("zh", tool_desc.get("en", ""))
    else:
        return tool_desc.get("en", tool_desc.get("zh", ""))

# 创建 MCP 服务器
mcp = FastMCP("Copilot-0 Knowledge Base MCP Server")

# 注册同步函数
@mcp.tool(
    name="create_knowledge_base",
    description=get_tool_description("create_knowledge_base")
)
def mcp_create_knowledge_base(
    kb_name: str,
    chunk_size: int,
    embedding_model: Optional[str] = None,
    embedding_endpoint: Optional[str] = None,
    embedding_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """创建知识库"""
    return create_knowledge_base(kb_name, chunk_size, embedding_model, embedding_endpoint, embedding_api_key)


@mcp.tool(
    name="delete_knowledge_base",
    description=get_tool_description("delete_knowledge_base")
)
def mcp_delete_knowledge_base(kb_name: str) -> Dict[str, Any]:
    """删除知识库"""
    return delete_knowledge_base(kb_name)


@mcp.tool(
    name="list_knowledge_bases",
    description=get_tool_description("list_knowledge_bases")
)
def mcp_list_knowledge_bases() -> Dict[str, Any]:
    """列出所有知识库"""
    return list_knowledge_bases()


@mcp.tool(
    name="select_knowledge_base",
    description=get_tool_description("select_knowledge_base")
)
def mcp_select_knowledge_base(kb_name: str) -> Dict[str, Any]:
    """选择知识库"""
    return select_knowledge_base(kb_name)


@mcp.tool(
    name="list_documents",
    description=get_tool_description("list_documents")
)
def mcp_list_documents() -> Dict[str, Any]:
    """列出文档"""
    return list_documents()


@mcp.tool(
    name="delete_document",
    description=get_tool_description("delete_document")
)
def mcp_delete_document(doc_name: str) -> Dict[str, Any]:
    """删除文档"""
    return delete_document(doc_name)


@mcp.tool(
    name="export_database",
    description=get_tool_description("export_database")
)
def mcp_export_database(export_path: str) -> Dict[str, Any]:
    """导出数据库"""
    return export_database(export_path)


@mcp.tool(
    name="import_database",
    description=get_tool_description("import_database")
)
def mcp_import_database(source_db_path: str) -> Dict[str, Any]:
    """导入数据库"""
    return import_database(source_db_path)


# 注册异步函数
@mcp.tool(
    name="import_document",
    description=get_tool_description("import_document")
)
async def mcp_import_document(file_paths: List[str], chunk_size: Optional[int] = None) -> Dict[str, Any]:
    """导入文档（异步，支持多文件并发导入）"""
    return await import_document(file_paths, chunk_size)


@mcp.tool(
    name="search",
    description=get_tool_description("search")
)
async def mcp_search(query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    """搜索（异步）"""
    return await search(query, top_k)


@mcp.tool(
    name="update_document",
    description=get_tool_description("update_document")
)
async def mcp_update_document(doc_name: str, chunk_size: int) -> Dict[str, Any]:
    """更新文档（异步）"""
    return await update_document(doc_name, chunk_size)


if __name__ == "__main__":
    # 启动 MCP 服务器
    # 使用 stdio transport，这是 MCP 工具的标准方式
    mcp.run(transport='sse')

