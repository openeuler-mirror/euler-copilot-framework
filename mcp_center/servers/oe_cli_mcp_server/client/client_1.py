# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Client"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Union
from pydantic import BaseModel, Field
from enum import Enum
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from mcp_center.servers.oe_cli_mcp_server.client.client import MCPClient

logger = logging.getLogger(__name__)


async def main() -> None:
    """测试MCP Client"""
    url = "http://0.0.0.0:12555/sse"
    headers = {}
    client = MCPClient(url, headers)
    await client.init()
    # ===================== 核心配置 =====================
    target_count = 100  # 要执行的总次数（可改为任意N）
    total_time = 1.0    # 总时长（1秒）
    # ====================================================

    print(f"\n开始在 {total_time} 秒内执行 {target_count} 次 sys_info_tool 调用...")
    print("="*60)

    # 定义单个调用任务（复用你的调用逻辑）
    async def tool_call_task():
        return await client.call_tool(
            "sys_info_tool",
            {"info_types": ["cpu", "mem", "disk", "os"]}
        )

    # 1. 均匀间隔启动所有任务（确保1秒内触发完）
    tasks = []
    interval = total_time / target_count  # 每个任务的启动间隔
    for _ in range(target_count):
        # 启动任务并加入列表（并发执行）
        task = asyncio.create_task(tool_call_task())
        tasks.append(task)
        # 间隔一段时间启动下一个，确保1秒内刚好启动完所有任务
        await asyncio.sleep(interval)

    # 2. 等待所有任务执行完成，并收集结果
    results = await asyncio.gather(*tasks)

    # 输出结果（可选：按需打印，也可以只返回results）
    print(f"\n{target_count} 次调用全部完成！")
    print("="*60)
    # 打印前3个结果示例（避免输出过多）
    for i in range(min(3, target_count)):
        print(f"第 {i+1} 次结果：{results[i]}")
    if target_count > 3:
        print(f"... 省略剩余 {target_count - 3} 次结果 ...")

    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
