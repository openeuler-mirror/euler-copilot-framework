import argparse

def parse_args():
    """解析命令行参数（仅保留核心参数，对齐原有命令）"""
    # 配置格式化器：保留换行符，让示例和描述更易读
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="mcp-server",
        description="mcp-server 命令行工具 - 用于管理MCP服务及工具包",
        formatter_class=formatter,
        epilog="""使用示例：
  工具包管理：
    mcp-server --add /path/to/xxx_tool       # 从目录新增工具包
    mcp-server --add custom_tool.zip         # 从ZIP包新增工具包
    mcp-server --remove file_tools           # 删除名为file_tools的工具包
    mcp-server --tool                        # 查看已加载的所有工具包
  
  服务管理：
    mcp-server --init                        # 初始化服务（仅保留基础运维包）
    mcp-server --start                       # 启动mcp-server服务
    mcp-server --stop                        # 终止mcp-server服务
    mcp-server --restart                     # 重启mcp-server服务
    mcp-server --log                         # 查看mcp-server实时日志
  
  帮助信息：
    mcp-server -h/--help                    # 查看完整帮助文档
        """
    )

    # 互斥命令组（一次一个核心操作）
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument(
        "--add",
        metavar="PATH",
        help="新增工具包（支持本地目录或ZIP压缩包路径，示例：-add /xxx_tool 或 -add custom.zip）"
    )
    command_group.add_argument(
        "--remove",
        metavar="TOOL_NAME",
        help="删除工具包（指定工具包名称，示例：-remove file_tools）"
    )
    command_group.add_argument(
        "--tool",
        action="store_true",
        help="查看已加载的所有工具包列表"
    )
    command_group.add_argument(
        "--init",
        action="store_true",
        help="初始化服务（重置工具包，仅保留基础运维包）"
    )
    command_group.add_argument(
        "--log",
        action="store_true",
        help="查看mcp-server服务实时日志（按Ctrl+C停止）"
    )
    command_group.add_argument(
        "--start",
        action="store_true",
        help="启动mcp-server服务（等价于systemctl start mcp-server）"
    )
    command_group.add_argument(
        "--stop",
        action="store_true",
        help="终止mcp-server服务（等价于systemctl stop mcp-server）"
    )
    command_group.add_argument(
        "--restart",
        action="store_true",
        help="重启mcp-server服务（等价于systemctl restart mcp-server）"
    )

    return parser.parse_args()
