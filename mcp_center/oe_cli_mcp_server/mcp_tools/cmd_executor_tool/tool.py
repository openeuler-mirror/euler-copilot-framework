import asyncio
from typing import Optional
from oe_cli_mcp_server.mcp_tools.cmd_executor_tool.base import init_response, get_msg, get_final_timeout, local_exec_sync, ssh_exec_sync


# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.


async def cmd_executor_tool(
        command: str = "",
        timeout: Optional[int] = None,
        host: str = "127.0.0.1"  # 新增：执行目标主机，默认本地
) -> dict:
    """
    命令执行工具（支持本地/SSH远程执行）
    :param command: 需要执行的shell命令/脚本（必填）
    :param timeout: 手动指定超时时间（秒），可选
    :param host: 执行目标主机（IP/主机名），默认127.0.0.1（本地）
    :return: 结构化字典结果
    """
    # 1. 初始化返回结果
    response = init_response()
    response["target"] = host  # 设置执行目标

    # 2. 命令为空校验
    if not command:
        response["message"] = get_msg("请提供需要执行的命令", "please give me the command to execute")
        return response

    # 3. 确定超时时间
    final_timeout = get_final_timeout(command, timeout)
    response["timeout_used"] = final_timeout

    # 4. 执行命令（本地/远程）
    def exec_wrapper():
        """执行包装函数（适配asyncio的run_in_executor）"""
        if host == "127.0.0.1" or host == "localhost":
            # 本地执行
            return local_exec_sync(command, final_timeout)
        else:
            # 远程SSH执行
            return ssh_exec_sync(host, command, final_timeout)

    try:
        # 异步执行同步函数（保留原有asyncio逻辑）
        loop = asyncio.get_running_loop()
        exec_success, exec_result, exec_msg = await asyncio.wait_for(
            loop.run_in_executor(None, exec_wrapper),
            timeout=final_timeout
        )

        # 5. 处理执行结果
        response["success"] = exec_success
        response["message"] = exec_msg
        response["result"] = exec_result

    except asyncio.TimeoutError:
        # 整体超时（asyncio的超时，兜底处理）
        response["message"] = get_msg(
            f"命令执行超时（{final_timeout}秒），已终止执行",
            f"Command execution timed out ({final_timeout} seconds), terminated"
        )
    except Exception as e:
        # 其他异常
        response["message"] = get_msg(
            f"命令执行出错：{str(e)}",
            f"Command execution failed: {str(e)}"
        )

    return response
