import argparse

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="rag-server 命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 创建知识库
    create_kb_parser = subparsers.add_parser("create_kb", help="创建知识库")
    create_kb_parser.add_argument("--kb_name", required=True, help="知识库名称")
    create_kb_parser.add_argument("--chunk_size", type=int, required=True, help="chunk大小（token数）")
    create_kb_parser.add_argument("--embedding_model", help="向量化模型名称")
    create_kb_parser.add_argument("--embedding_endpoint", help="向量化服务端点URL")
    create_kb_parser.add_argument("--embedding_api_key", help="向量化服务API Key")

    # 删除知识库
    delete_kb_parser = subparsers.add_parser("delete_kb", help="删除知识库")
    delete_kb_parser.add_argument("--kb_name", required=True, help="知识库名称")

    # 列出知识库
    subparsers.add_parser("list_kb", help="列出所有知识库")

    # 选择知识库
    select_kb_parser = subparsers.add_parser("select_kb", help="选择知识库")
    select_kb_parser.add_argument("--kb_name", required=True, help="知识库名称")

    # 导入文档
    import_doc_parser = subparsers.add_parser("import_doc", help="导入文档")
    import_doc_parser.add_argument("--file_paths", nargs="+", required=True, help="文件路径列表（绝对路径）")
    import_doc_parser.add_argument("--chunk_size", type=int, help="chunk大小（可选，默认使用知识库的chunk_size）")

    # 列出文档
    subparsers.add_parser("list_doc", help="列出文档")

    # 删除文档
    delete_doc_parser = subparsers.add_parser("delete_doc", help="删除文档")
    delete_doc_parser.add_argument("--doc_name", required=True, help="文档名称")

    # 更新文档
    update_doc_parser = subparsers.add_parser("update_doc", help="更新文档")
    update_doc_parser.add_argument("--doc_name", required=True, help="文档名称")
    update_doc_parser.add_argument("--chunk_size", type=int, required=True, help="新的chunk大小（token数）")

    # 搜索
    search_parser = subparsers.add_parser("search", help="搜索文档")
    search_parser.add_argument("--query", required=True, help="查询文本")
    search_parser.add_argument("--top_k", type=int, help="返回数量（可选，默认5）")

    # 导出数据库
    export_db_parser = subparsers.add_parser("export_db", help="导出数据库")
    export_db_parser.add_argument("--export_path", required=True, help="导出路径（绝对路径）")

    # 导入数据库
    import_db_parser = subparsers.add_parser("import_db", help="导入数据库")
    import_db_parser.add_argument("--source_db_path", required=True, help="源数据库文件路径（绝对路径）")

    return parser.parse_args()

