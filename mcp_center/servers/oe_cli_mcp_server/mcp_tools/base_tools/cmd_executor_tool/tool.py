# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
import asyncio
import subprocess

from config.public.base_config_loader import BaseConfig, LanguageEnum

# Shell脚本执行的默认超时时间（秒）
SHELL_SCRIPT_DEFAULT_TIMEOUT = 600


async def cmd_executor_tool(  # noqa: C901
    command: str = "",
    timeout: int | None = None,
) -> dict:
    """
    本地命令执行工具，支持按指令类型自动设置超时，返回结构化字典结果（多语言）

    :param host: 兼容保留参数，无实际作用
    :param command: 需要执行的shell命令/脚本（必填）
    :param timeout: 手动指定超时时间（秒），可选
    :return: 结构化字典结果，包含success、message、result、target、timeout_used
    """
    # -------------------------- 读取语言配置（优先级：传入参数 > 配置文件） --------------------------

    lang = BaseConfig().get_config().public_config.language

    # -------------------------- 初始化返回结果字典 --------------------------
    response = {
        "success": False,  # 执行状态：True成功/False失败
        "message": "",  # 提示信息（多语言）
        "result": "",  # 命令执行结果（成功时为输出内容，失败时为空）
        "target": "127.0.0.1",  # 执行目标，固定为本地
        "timeout_used": 0,  # 实际使用的超时时间（秒）
    }

    # -------------------------- 命令为空校验 --------------------------
    if not command:
        response["message"] = (
            "请提供需要执行的命令" if lang == LanguageEnum.ZH else "please give me the command to execute"
        )
        return response

    # -------------------------- 超时时间配置与处理 --------------------------
    # 定义常见指令的默认超时时间（秒），可根据需求扩展
    cmd_timeout_map = {
        # 快速指令：短超时
        "ls": 5,
        "pwd": 5,
        "echo": 5,
        "cat": 10,
        "grep": 10,
        # 中等耗时指令
        "ping": 30,
        "curl": 30,
        # 长耗时指令
        "yum": 300,
        "apt": 300,
        "docker": 600,
        "scp": 600,
    }

    def get_final_timeout(cmd: str) -> int:
        """确定最终超时时间，优先级：用户指定 > Shell脚本默认 > 普通指令默认 > 全局默认15秒"""
        # 优先级1：用户手动指定超时（校验合法性）
        if timeout is not None:
            try:
                t = int(timeout)
            except (ValueError, TypeError):
                return 15
            else:
                return t if t > 0 else 15
        # 优先级2：执行Shell脚本的指令，使用专属超时
        cmd_lower = cmd.lower()
        if ".sh" in cmd_lower or cmd_lower.startswith(("bash ", "sh ")):
            return SHELL_SCRIPT_DEFAULT_TIMEOUT
        # 优先级3：匹配普通指令的默认超时
        for cmd_key, t in cmd_timeout_map.items():
            if cmd_key in cmd_lower:
                return t
        # 优先级4：全局默认超时
        return 15

    final_timeout = get_final_timeout(command)
    response["timeout_used"] = final_timeout  # 记录实际使用的超时时间

    # -------------------------- 本地命令执行（同步逻辑，供线程池调用） --------------------------
    def local_exec_sync():
        """同步执行本地命令，返回 (returncode, stdout, stderr, exception)"""
        try:
            result = subprocess.run(  # noqa: S602
                command,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
            )
            return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip(), None
        except Exception as e:  # noqa: BLE001
            # 其他异常，返回异常信息
            return None, "", "", e

    # -------------------------- 超时控制执行 --------------------------
    try:
        loop = asyncio.get_running_loop()
        # 用线程池执行同步的本地命令，并用wait_for控制超时
        returncode, exec_stdout, exec_stderr, exec_exception = await asyncio.wait_for(
            loop.run_in_executor(None, local_exec_sync),
            timeout=final_timeout,
        )

        if exec_exception is not None:
            response["message"] = (
                f"本地执行命令出错：{exec_exception!s}"
                if lang == LanguageEnum.ZH
                else f"Local command execution failed: {exec_exception!s}"
            )
            return response

        # 约定：returncode==0 为成功。
        # 特例：grep 在“无匹配”时通常返回 1，这对很多排查类命令并不表示执行失败。
        # 例如：ss -tuln | grep ':8080' 当端口不存在时应视为“成功但无结果”，否则上层可能会误判为失败并反复重试。
        cmd_lower = command.lower()
        is_grep_no_match = (returncode == 1) and ("grep" in cmd_lower) and (exec_stderr == "")

        if returncode == 0 or is_grep_no_match:
            response["success"] = True
            if is_grep_no_match:
                response["message"] = (
                    "命令执行成功（未匹配到结果）"
                    if lang == LanguageEnum.ZH
                    else "Command executed successfully (no matches found)"
                )
            else:
                response["message"] = "命令执行成功" if lang == LanguageEnum.ZH else "Command executed successfully"
            response["result"] = exec_stdout
        else:
            # 命令执行失败：优先展示 stderr，其次展示 stdout（避免 stderr 为空时无信息）
            err_text = exec_stderr or exec_stdout or ""
            response["message"] = (
                f"命令执行出错（exit_code={returncode}）：{err_text}"
                if lang == LanguageEnum.ZH
                else f"Command execution failed (exit_code={returncode}): {err_text}"
            )

    except TimeoutError:
        # 命令执行超时
        response["message"] = (
            f"本地执行命令超时（{final_timeout}秒），已终止执行"
            if lang == LanguageEnum.ZH
            else f"Local command execution timed out ({final_timeout} seconds), terminated"
        )
    except Exception as e:  # noqa: BLE001
        # 其他执行异常（如线程池错误）
        response["message"] = (
            f"本地执行命令出错：{e!s}" if lang == LanguageEnum.ZH else f"Local command execution failed: {e!s}"
        )

    return response
