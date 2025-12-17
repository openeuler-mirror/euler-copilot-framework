import argparse

def parse_args():
    """解析命令行参数（仅保留核心参数，对齐原有命令）"""
    parser = argparse.ArgumentParser(description="mcp-server 命令行工具")

    # 互斥命令组（一次一个核心操作）
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument("-add", metavar="包名/zip路径", help="新增工具包（示例：-add 智算调优 或 -add ./custom.zip）")
    command_group.add_argument("-remove", metavar="包名", help="删除工具包（示例：-remove 智算调优）")
    command_group.add_argument("-tool", action="store_true", help="查看已加载工具包")
    command_group.add_argument("-init", action="store_true", help="初始化服务（仅保留基础运维包）")
    command_group.add_argument("-log", action="store_true", help="查看服务实时日志")
    command_group.add_argument("-start", action="store_true", help="启动 mcp-server 服务")
    command_group.add_argument("-stop", action="store_true", help="终止 mcp-server 服务")
    command_group.add_argument("-restart", action="store_true", help="重启 mcp-server 服务")
    command_group.add_argument("-llm", action="store_true", help="配置大模型（需配合 --model/--apikey/--name）")
    command_group.add_argument("-config", metavar="键=值", help="修改公共配置（示例：-config language=en）")

    # 大模型配置附属参数
    parser.add_argument("--model", help="大模型地址（如 http://127.0.0.1:8000）")
    parser.add_argument("--apikey", help="大模型 API 密钥")
    parser.add_argument("--name", help="大模型名称（如 qwen、gpt-3.5）")

    return parser.parse_args()