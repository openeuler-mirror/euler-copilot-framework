#!/usr/bin/env python3
import argparse

from mcp_service_manager import McpServiceManager


def main():
    """MCP服务管理CLI工具 - 带完整帮助信息"""
    # 主解析器：配置全局帮助信息
    parser = argparse.ArgumentParser(
        prog="mcp-manager",
        description="MCP系统服务管理工具 - 管理systemd的.service服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,  # 保留换行符，让示例更易读
        epilog="""使用示例：
  单个服务操作：
    mcp-manager start rag.service        # 启动rag.service服务
    mcp-manager stop rag.service         # 停止rag.service服务
    mcp-manager restart rag.service      # 重启rag.service服务
    mcp-manager status rag.service       # 查看rag.service状态
    mcp-manager logs rag.service         # 查看rag.service最后100行日志
    mcp-manager logs rag.service -n 200  # 查看rag.service最后200行日志
    mcp-manager logs rag.service -f      # 实时跟踪rag.service日志（Ctrl+C停止）
  
  批量操作：
    mcp-manager start all                # 批量启动所有.service服务
    mcp-manager stop all                 # 批量停止所有.service服务
    
  查看运行中服务：
    mcp-manager mcp                      # 列出所有正在运行的MCP服务
        """
    )

    # 子命令解析器：配置每个子命令的帮助信息
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # 1. start 命令：启动服务（单个/all）
    parser_start = subparsers.add_parser(
        "start",
        help="启动服务（单个服务或所有服务）",
        description="启动指定的.service服务，支持单个服务或批量启动所有服务"
    )
    parser_start.add_argument(
        "target",
        help="启动目标：单个.service文件名（如 rag.service） 或 all（批量启动所有）"
    )

    # 2. stop 命令：停止服务（单个/all）
    parser_stop = subparsers.add_parser(
        "stop",
        help="停止服务（单个服务或所有服务）",
        description="停止指定的.service服务，支持单个服务或批量停止所有服务"
    )
    parser_stop.add_argument(
        "target",
        help="停止目标：单个.service文件名（如 rag.service） 或 all（批量停止所有）"
    )

    # 3. restart 命令：重启单个服务
    parser_restart = subparsers.add_parser(
        "restart",
        help="重启单个.service服务",
        description="重启指定的单个.service服务（不支持批量重启）"
    )
    parser_restart.add_argument(
        "service",
        help="要重启的.service文件名（如 rag.service）"
    )

    # 4. status 命令：查询单个服务状态
    parser_status = subparsers.add_parser(
        "status",
        help="查询单个.service服务状态",
        description="查询指定的单个.service服务状态（等价于 systemctl status xxx.service --no-pager）"
    )
    parser_status.add_argument(
        "service",
        help="要查询的.service文件名（如 rag.service）"
    )

    # 5. logs 命令：查看服务日志
    parser_logs = subparsers.add_parser(
        "logs",
        help="查看.service服务日志",
        description="查看指定的.service服务日志，支持查看指定行数或实时跟踪"
    )
    parser_logs.add_argument(
        "service",
        help="要查看日志的.service文件名（如 rag.service）"
    )
    parser_logs.add_argument(
        "--lines", "-n",
        type=int,
        default=100,
        help="查看最后N行日志（默认：100行）"
    )
    parser_logs.add_argument(
        "--follow", "-f",
        action="store_true",
        help="实时跟踪日志（类似 tail -f，按Ctrl+C停止）"
    )
    parser_mcp = subparsers.add_parser(
        "mcp",
        help="列出所有正在运行的MCP服务",
        description="列出service目录下所有状态为 active (running) 的MCP .service服务"
    )

    # 解析参数
    args = parser.parse_args()

    # 初始化管理器
    manager = McpServiceManager()

    # 执行命令：极致简洁，仅输出原生命令结果
    try:
        if args.command == "start":
            if args.target.lower() == "all":
                manager.start_all()
            else:
                manager.start(args.target)
        elif args.command == "stop":
            if args.target.lower() == "all":
                manager.stop_all()
            else:
                manager.stop(args.target)
        elif args.command == "restart":
            manager.restart(args.service)
        elif args.command == "status":
            manager.get_status(args.service)
        elif args.command == "logs":
            manager.get_logs(args.service, lines=args.lines, follow=args.follow)
        elif args.command == "mcp":
            # 列出所有运行中的服务并友好展示
            running_services = manager.list_running_services()
            print("===== 正在运行的MCP服务 =====")
            if running_services:
                for idx, service in enumerate(running_services, 1):
                    print(f"{idx}. {service}")
            else:
                print("暂无正在运行的MCP服务")
            print("============================")
    except Exception as e:
        print(f"错误：{str(e)}")
        exit(1)

if __name__ == "__main__":
    main()