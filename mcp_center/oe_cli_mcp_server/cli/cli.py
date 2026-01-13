#!/usr/bin/python3
import logging
import sys

from parse_args import parse_args
with open("/etc/systemd/system/mcp-server.service", "r") as f:
    for line in f:
        if line.strip().startswith("WorkingDirectory="):
            PROJECT_ROOT = line.strip().split("=", 1)[1]
            break

# 加入 sys.path
sys.path.insert(0, PROJECT_ROOT)
from handle import (
    handle_add, handle_remove, handle_tool, handle_init,
    handle_start, handle_log, handle_stop,handle_restart
)


# 日志极简配置
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def main():
    args = parse_args()
    success = False

    # 命令调度（直接映射，无冗余）
    if args.add:
        success = handle_add(args.add)
    elif args.remove:
        success = handle_remove(args.remove)
    elif args.tool:
        success = handle_tool()
    elif args.init:
        success = handle_init()
    elif args.start:
        success = handle_start()
    elif args.restart:
        success = handle_restart()
    elif args.log:
        success = handle_log()
    elif args.stop:
        success = handle_stop()

    raise SystemExit(0 if success else 1)

if __name__ == "__main__":
    main()