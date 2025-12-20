import asyncio
from typing import Optional
import subprocess
from servers.oe_cli_mcp_server.mcp_tools.base_tools.cmd_executor_tool.base import replace_cmd_with_abs_path
from config.public.base_config_loader import BaseConfig, LanguageEnum
import re

# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.


async def cmd_executor_tool(
        command: str = "",
        timeout: Optional[int] = None,
) -> dict:
    """
    本地命令执行工具，支持按指令类型自动设置超时，返回结构化字典结果（多语言）
    :param command: 需要执行的shell命令/脚本（必填）
    :param timeout: 手动指定超时时间（秒），可选
    :return: 结构化字典结果，包含success、message、result、target、timeout_used
    """
    # -------------------------- 读取语言配置 --------------------------
    # 改为使用传入的参数，方便测试多语言
    current_lang = BaseConfig().get_config().public_config.language

    # -------------------------- 初始化返回结果字典 --------------------------
    response = {
        "success": False,  # 执行状态：True成功/False失败
        "message": "",     # 提示信息（多语言）
        "result": "",      # 命令执行结果（成功时为输出内容，失败时为空）
        "target": "127.0.0.1",  # 执行目标，固定为本地
        "timeout_used": 0  # 实际使用的超时时间（秒）
    }

    # -------------------------- 命令为空校验 --------------------------
    if not command:
        response["message"] = "请提供需要执行的命令" if current_lang == LanguageEnum.ZH else "please give me the command to execute"
        return response

    # -------------------------- 超时时间配置与处理 --------------------------
    cmd_timeout_map = {
        "ls": 5, "pwd": 5, "echo": 5, "cat": 10, "grep": 10,
        "ping": 30, "curl": 30, "yum": 300, "apt": 300, "docker": 600, "scp": 600,
    }
    SHELL_SCRIPT_DEFAULT_TIMEOUT = 600

    def get_final_timeout(cmd: str) -> int:
        """确定最终超时时间"""
        if timeout is not None:
            try:
                t = int(timeout)
                return t if t > 0 else 15
            except (ValueError, TypeError):
                return 15
        cmd_lower = cmd.lower()
        split_pattern = re.compile(r'(\|\||&&|\||;|&)')  # 匹配所有命令连接符
        cmd_parts = [part.strip()
                     for part in split_pattern.split(cmd_lower) if part.strip()]
        t_used = 0
        for part in cmd_parts:
            if part in ["||", "&&", "|", ";", "&"]:
                continue
            if ".sh" in part or part.startswith("bash ") or part.startswith("sh "):
                t_used += SHELL_SCRIPT_DEFAULT_TIMEOUT
                continue
            for cmd_key, t in cmd_timeout_map.items():
                if part.startswith(cmd_key) or part == cmd_key:
                    t_used += t
        return t_used

    final_timeout = get_final_timeout(command)
    response["timeout_used"] = final_timeout
    command = replace_cmd_with_abs_path(command)
    # -------------------------- 本地命令执行 --------------------------

    def local_exec_sync():
        """同步执行本地命令，优化空结果和错误处理"""
        try:
            # 关键修改1：移除check=True，手动处理退出码
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 提取输出和错误信息
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # 关键修改2：区分不同场景
            if result.returncode == 0:
                # 场景1：命令执行成功（退出码0）
                if not stdout:
                    # 子场景1.1：执行成功但无输出结果
                    return True, "", "命令执行成功但未返回任何结果" if current_lang == LanguageEnum.ZH else "Command executed successfully but no results returned"
                # 子场景1.2：执行成功且有输出结果
                return True, stdout, ""
            else:
                # 场景2：命令执行失败（非0退出码）
                # 特殊处理grep命令：退出码1表示无匹配结果，不算真正的执行失败
                cmd_lower = command.lower()
                if "grep" in cmd_lower and result.returncode == 1:
                    return True, "", "未找到匹配内容" if current_lang == LanguageEnum.ZH else "No matching content found"

                # 真正的执行失败，合并错误信息
                error_msg = stderr or stdout or f"命令执行失败，退出码：{result.returncode}"
                return False, "", error_msg

        except Exception as e:
            # 场景3：其他异常（如命令不存在、权限问题等）
            return False, "", f"执行异常：{str(e)}"

    # -------------------------- 超时控制执行 --------------------------
    try:
        loop = asyncio.get_running_loop()
        exec_success, exec_result, exec_error = await asyncio.wait_for(
            loop.run_in_executor(None, local_exec_sync),
            timeout=final_timeout
        )

        if exec_success:
            # 命令执行成功（包括空结果场景）
            response["success"] = True
            # 优先使用自定义提示，无则用默认成功提示
            response["message"] = exec_error if exec_error else (
                "命令执行成功" if current_lang == LanguageEnum.ZH else "Command executed successfully")
            response["result"] = exec_result
        else:
            # 命令真正执行失败
            if not exec_error:
                exec_error = "未知错误" if current_lang == LanguageEnum.ZH else "Unknown error"
            response["message"] = f"命令执行出错：{exec_error}" if current_lang == LanguageEnum.ZH else f"Command execution failed: {exec_error}"

    except asyncio.TimeoutError:
        response[
            "message"] = f"本地执行命令超时（{final_timeout}秒），已终止执行" if current_lang == LanguageEnum.ZH else f"Local command execution timed out ({final_timeout} seconds), terminated"
    except Exception as e:
        response["message"] = f"本地执行命令出错：{str(e)}" if current_lang == LanguageEnum.ZH else f"Local command execution failed: {str(e)}"

    return response
