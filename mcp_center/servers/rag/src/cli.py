#!/usr/bin/env python3
"""
RAG Server CLI 工具
用于直接调用 RAG 工具函数的命令行接口
"""
import os
import sys

# 从 systemd service 文件读取工作目录
SERVICE_FILE = "/etc/systemd/system/rag.service"
PROJECT_ROOT = "/usr/lib/euler-copilot-framework/mcp_center"
if os.path.exists(SERVICE_FILE):
    with open(SERVICE_FILE, "r") as f:
        for line in f:
            if line.strip().startswith("WorkingDirectory="):
                PROJECT_ROOT = line.strip().split("=", 1)[1]
                break

# 添加项目根目录到 sys.path
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 导入 CLI 模块
from cli.parse_args import parse_args
from cli.handle import (
    handle_create_kb,
    handle_delete_kb,
    handle_list_kb,
    handle_select_kb,
    handle_import_doc,
    handle_list_doc,
    handle_delete_doc,
    handle_update_doc,
    handle_search,
    handle_export_db,
    handle_import_db
)

def main():
    """主函数"""
    args = parse_args()
    
    if not args.command:
        print("❌ 请指定命令，使用 --help 查看帮助")
        sys.exit(1)
    
    success = False

    # 命令调度
    if args.command == "create_kb":
        success = handle_create_kb(args)
    elif args.command == "delete_kb":
        success = handle_delete_kb(args)
    elif args.command == "list_kb":
        success = handle_list_kb(args)
    elif args.command == "select_kb":
        success = handle_select_kb(args)
    elif args.command == "import_doc":
        success = handle_import_doc(args)
    elif args.command == "list_doc":
        success = handle_list_doc(args)
    elif args.command == "delete_doc":
        success = handle_delete_doc(args)
    elif args.command == "update_doc":
        success = handle_update_doc(args)
    elif args.command == "search":
        success = handle_search(args)
    elif args.command == "export_db":
        success = handle_export_db(args)
    elif args.command == "import_db":
        success = handle_import_db(args)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

