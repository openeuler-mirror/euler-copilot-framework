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


logger = logging.getLogger(__name__)


class MCPStatus(str, Enum):
    """MCP状态枚举"""
    UNINITIALIZED = "UNINITIALIZED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class MCPClient:
    """MCP客户端基类"""

    def __init__(self, url: str, headers: dict[str, str]) -> None:
        """初始化MCP Client"""
        self.url = url
        self.headers = headers
        self.client: Union[ClientSession, None] = None
        self.status = MCPStatus.UNINITIALIZED

    async def _main_loop(
        self
    ) -> None:
        """
        创建MCP Client

        抽象函数；作用为在初始化的时候使用MCP SDK创建Client
        由于目前MCP的实现中Client和Session是1:1的关系，所以直接创建了 :class:`~mcp.ClientSession`
        """
        # 创建Client
        try:
            client = sse_client(
                url=self.url,
                headers=self.headers
            )
        except Exception as e:
            self.error_sign.set()
            err = f"创建Client失败，错误信息：{e}"
            print(err)
            raise Exception(err)
        # 创建Client、Session
        try:
            exit_stack = AsyncExitStack()
            read, write = await exit_stack.enter_async_context(client)
            self.client = ClientSession(read, write)
            session = await exit_stack.enter_async_context(self.client)
            # 初始化Client
            await session.initialize()
        except Exception:
            self.error_sign.set()
            self.status = MCPStatus.STOPPED
            err = f"初始化Client失败，错误信息：{e}"
            print(err)
            raise

        self.ready_sign.set()
        self.status = MCPStatus.RUNNING
        # 等待关闭信号
        await self.stop_sign.wait()

        # 关闭Client
        try:
            await exit_stack.aclose()  # type: ignore[attr-defined]
            self.status = MCPStatus.STOPPED
        except Exception:
            print(f"关闭Client失败，错误信息：{e}")

    async def init(self) -> None:
        """
        初始化 MCP Client类
        :return: None
        """
        # 初始化变量
        self.ready_sign = asyncio.Event()
        self.error_sign = asyncio.Event()
        self.stop_sign = asyncio.Event()

        # 创建协程
        self.task = asyncio.create_task(self._main_loop())

        # 等待初始化完成
        done, pending = await asyncio.wait(
            [asyncio.create_task(self.ready_sign.wait()),
             asyncio.create_task(self.error_sign.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        if self.error_sign.is_set():
            self.status = MCPStatus.ERROR
            print("MCP Client 初始化失败")
            raise Exception("MCP Client 初始化失败")

    async def call_tool(self, tool_name: str, params: dict) -> "CallToolResult":
        """调用MCP Server的工具"""
        return await self.client.call_tool(tool_name, params)

    async def stop(self) -> None:
        """停止MCP Client"""
        self.stop_sign.set()
        try:
            await self.task
        except Exception as e:
            err = f"关闭MCP Client失败，错误信息：{e}"
            print(err)


async def main() -> None:
    """测试MCP Client"""
    url = "http://0.0.0.0:12555/sse"
    headers = {}
    client = MCPClient(url, headers)
    await client.init()

    # 初始化时多余的调用移除，保留下方有序测试用例
    # ==================================
    # 1. sys_info_tool 测试用例（3个，修复无效枚举值）
    # ==================================
    print("\n" + "="*60)
    print("1. sys_info_tool - 采集CPU+内存+磁盘+系统信息")
    print("="*60)
    result = await client.call_tool("sys_info_tool", {"info_types": ["cpu", "mem", "disk", "os"]})
    print(result)

    print("\n" + "="*60)
    print("2. sys_info_tool - 单独采集网络信息（IP/网卡）")
    print("="*60)
    result = await client.call_tool("sys_info_tool", {"info_types": ["net"]})
    print(result)

    print("\n" + "="*60)
    print("3. sys_info_tool - 采集安全信息（SELinux+防火墙）")
    print("="*60)
    result = await client.call_tool("sys_info_tool", {"info_types": ["selinux", "firewall"]})
    print(result)

    # 移除无效的 "kernel" 和 "all" 类型测试（工具不支持）

    # ==================================
    # 2. file_tool 测试用例（4个，修复枚举值、参数名）
    # ==================================
    print("\n" + "="*60)
    print("4. file_tool - 列出 /etc 目录下的 .conf 配置文件（过滤关键词）")
    print("="*60)
    # 用 ls + 后续过滤实现（工具无find枚举，参数名改为file_path）
    result = await client.call_tool("file_tool", {
        "action": "ls",
        "file_path": "/etc",
        "detail": False,
        "encoding": "utf-8"
    })
    print(result)

    print("\n" + "="*60)
    print("5. file_tool - 读取 /etc/os-release 文件内容（系统版本）")
    print("="*60)
    # action改为cat，参数名改为file_path
    result = await client.call_tool("file_tool", {
        "action": "cat",
        "file_path": "/etc/os-release",
        "encoding": "utf-8"
    })
    print(result)

    print("\n" + "="*60)
    print("6. file_tool - 新建临时文件并写入内容")
    print("="*60)
    # 工具无find/mtime枚举，替换为add+edit实用场景
    result = await client.call_tool("file_tool", {
        "action": "add",
        "file_path": "/tmp/file_tool_test.txt",
        "overwrite": True
    })
    print("新建文件结果：", result)
    result = await client.call_tool("file_tool", {
        "action": "edit",
        "file_path": "/tmp/file_tool_test.txt",
        "content": "file_tool测试内容\n系统版本：Ubuntu 22.04",
        "encoding": "utf-8"
    })
    print("写入内容结果：", result)

    print("\n" + "="*60)
    print("7. file_tool - 修改 /tmp/file_tool_test.txt 权限为755")
    print("="*60)
    # action改为chmod，参数名改为file_path
    result = await client.call_tool("file_tool", {
        "action": "chmod",
        "file_path": "/tmp/file_tool_test.txt",
        "mode": "755"
    })
    print(result)

    # ==================================
    # 3. pkg_tool 测试用例（4个，修复无效枚举、参数）
    # ==================================
    print("\n" + "="*60)
    print("8. pkg_tool - 列出已安装的所有 nginx 相关包")
    print("="*60)
    result = await client.call_tool("pkg_tool", {
        "action": "list",
        "filter_key": "nginx"
    })
    print(result)

    print("\n" + "="*60)
    print("9. pkg_tool - 查询 openssh-server 包详情（版本/依赖）")
    print("="*60)
    result = await client.call_tool("pkg_tool", {
        "action": "info",
        "pkg_name": "openssh-server"
    })
    print(result)

    print("\n" + "="*60)
    print("10. pkg_tool - 安装 nginx 包 + 验证安装结果")
    print("="*60)

    # 步骤1：安装 nginx 包（双系统兼容，自动适配 apt/dnf）
    print("正在安装 nginx 包...")
    install_result = await client.call_tool("pkg_tool", {
        "action": "install",  # 安装动作（双系统兼容）
        "pkg_name": "nginx",  # 要安装的包名
        "yes": True           # 自动确认安装（避免交互）
    })
    print("安装执行结果：")
    print(install_result)

    # 步骤2：验证安装结果（用 list 方法过滤 nginx 相关包）
    print("\n" + "-"*40)
    print("验证：查询已安装的 nginx 相关包")
    print("-"*40)
    verify_result = await client.call_tool("pkg_tool", {
        "action": "list",      # 列出已安装包
        "filter_key": "nginx"  # 过滤关键词（只显示 nginx 相关）
    })
    print("验证结果：")
    print(verify_result)

    print("\n" + "="*60)
    print("11. pkg_tool - 清理 yum/dnf 包缓存（all类型）")
    print("="*60)
    result = await client.call_tool("pkg_tool", {
        "action": "clean",
        "cache_type": "all",
        "yes": True
    })
    print(result)

    # ==================================
    # 4. proc_tool 测试用例（4个，修复无效枚举、参数）
    # ==================================
    print("\n" + "="*60)
    print("12. proc_tool - 查找所有 systemd 相关进程")
    print("="*60)
    result = await client.call_tool("proc_tool", {
        "proc_actions": ["find"],
        "proc_name": "systemd"
    })
    print(result)

    print("\n" + "="*60)
    print("13. proc_tool - 查询 PID=1 进程（systemd）资源占用")
    print("="*60)
    result = await client.call_tool("proc_tool", {
        "proc_actions": ["stat"],
        "pid": 1
    })
    print(result)

    print("\n" + "="*60)
    print("14. proc_tool - 列出所有进程（后续可筛选CPU占用前5）")
    print("="*60)
    # 工具无top枚举，用list获取所有进程（业务层可筛选）
    result = await client.call_tool("proc_tool", {
        "proc_actions": ["list"]
    })
    print(result)

    print("\n" + "="*60)
    print("15. proc_tool - 重启 sshd 服务（systemd服务）")
    print("="*60)
    # 工具无tree枚举，替换为restart实用场景
    result = await client.call_tool("proc_tool", {
        "proc_actions": ["restart"],
        "service_name": "ssh"  # Ubuntu中sshd服务名为ssh
    })
    print(result)

    # 清理临时文件
    print("\n" + "="*60)
    print("16. file_tool - 删除临时测试文件")
    print("="*60)
    result = await client.call_tool("file_tool", {
        "action": "delete",
        "file_path": "/tmp/file_tool_test.txt"
    })
    print(result)

    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
