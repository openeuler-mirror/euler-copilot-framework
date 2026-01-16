import logging
import os
import re
import shlex
import time

import paramiko

from config.public.base_config_loader import BaseConfig, LanguageEnum
import subprocess
from typing import Tuple, Optional, Dict

# 超时配置（抽离为常量，便于维护）
CMD_TIMEOUT_MAP = {
    "ls": 5, "pwd": 5, "echo": 5, "cat": 10, "grep": 10,
    "ping": 30, "curl": 30, "yum": 300, "apt": 300, "docker": 600, "scp": 600,
}
SHELL_SCRIPT_DEFAULT_TIMEOUT = 600

lang = BaseConfig().get_config().public_config.language
logger = logging.getLogger("cmd_executor_tool")
logger.setLevel(logging.INFO)

def init_response() -> Dict:
    """初始化返回结果字典（结构化）"""
    return {
        "success": False,
        "message": "",
        "result": "",
        "target": "127.0.0.1",
        "timeout_used": 0
    }

def get_final_timeout(command: str, manual_timeout: Optional[int]) -> int:
    """确定最终超时时间（公共逻辑抽离）"""
    # 1. 优先使用手动指定的超时时间
    if manual_timeout is not None:
        try:
            t = int(manual_timeout)
            return t if t > 0 else 15
        except (ValueError, TypeError):
            return 15
    # 2. 自动根据命令类型计算超时
    cmd_lower = command.lower()
    split_pattern = re.compile(r'(\|\||&&|\||;|&)')
    cmd_parts = [part.strip() for part in split_pattern.split(cmd_lower) if part.strip()]
    t_used = 0
    for part in cmd_parts:
        if part in ["||", "&&", "|", ";", "&"]:
            continue
        if ".sh" in part or part.startswith("bash ") or part.startswith("sh "):
            t_used += SHELL_SCRIPT_DEFAULT_TIMEOUT
            continue
        for cmd_key, t in CMD_TIMEOUT_MAP.items():
            if part.startswith(cmd_key) or part == cmd_key:
                t_used += t
    return t_used if t_used > 0 else 15  # 兜底：至少15秒

def get_msg(zh_msg: str, en_msg: str) -> str:
    """多语言提示信息"""
    return zh_msg if lang == LanguageEnum.ZH else en_msg

# ----------------------------------绝对路径执行cmd指令---------------------------------------
def get_absolute_command_path(cmd_name: str) -> str:
    """
    获取单个命令的绝对路径兜底遍历常见路径
    :param cmd_name: 命令名（如 ps、grep、python）
    :return: 绝对路径，找不到返回原命令名
    """
    # 兜底遍历常见路径（适配无 which 的极简系统）
    common_paths = ["/usr/bin", "/bin", "/usr/sbin",
                    "/sbin", "/usr/local/bin", "/usr/local/sbin"]
    for path in common_paths:
        abs_path = os.path.join(path, cmd_name)
        if os.path.exists(abs_path) and os.access(abs_path, os.X_OK):
            logger.info(f"兜底找到命令 {cmd_name} 的绝对路径：{abs_path}")
            return abs_path
    # 找不到路径，返回原命令名（执行时可能报错，由上层处理）
    logger.warning(f"未找到命令 {cmd_name} 的绝对路径，将使用原命令执行")
    return cmd_name


def replace_cmd_with_abs_path(cmd_str: str) -> str:
    """
    将命令字符串中的主程序替换为绝对路径（支持复杂命令：管道、参数、引号）
    :param cmd_str: 原始命令字符串（如 "ps aux | grep python"、"echo 'hello world'"）
    :return: 替换后的命令字符串（如 "/usr/bin/ps aux | /usr/bin/grep python"）
    """
    # 步骤1：拆分命令为「原子单元」（按管道/分号/&&/|| 拆分，保留连接符）
    import re
    split_pattern = re.compile(r'(\|\||&&|\||;|&)')  # 匹配所有命令连接符
    cmd_parts = [part.strip()
                 for part in split_pattern.split(cmd_str) if part.strip()]

    rebuilt_parts = []
    for part in cmd_parts:
        # 如果是连接符（如 |、&&、;），直接保留
        if part in ["||", "&&", "|", ";", "&"]:
            rebuilt_parts.append(part)
            continue

        # 步骤2：安全拆分子命令（处理引号/空格，如 echo "hello world"）
        try:
            sub_cmd_parts = shlex.split(part)
            if not sub_cmd_parts:
                rebuilt_parts.append(part)
                continue
        except ValueError as e:
            logger.error(f"解析子命令 {part} 失败：{e}，保留原内容")
            rebuilt_parts.append(part)
            continue

        # 步骤3：替换主程序为绝对路径（如 ps → /usr/bin/ps）
        main_cmd = sub_cmd_parts[0]
        abs_main_cmd = get_absolute_command_path(main_cmd)
        sub_cmd_parts[0] = abs_main_cmd

        # 步骤4：重组子命令（恢复引号/空格格式）
        rebuilt_sub_cmd = shlex.join(sub_cmd_parts)
        rebuilt_parts.append(rebuilt_sub_cmd)

    # 步骤5：拼接所有部分，得到最终命令字符串
    final_cmd = " ".join(rebuilt_parts)
    logger.info(f"原始命令：{cmd_str}")
    logger.info(f"绝对路径命令：{final_cmd}")
    return final_cmd

# -------------------------- 本地命令执行 --------------------------
def local_exec_sync(command: str, timeout: int) -> Tuple[bool, str, str]:
    """
    同步执行本地命令
    :param command: 待执行的命令
    :param timeout: 超时时间（秒，这里仅用于兼容，本地subprocess的超时在主函数处理）
    :return: (执行是否成功, 输出结果, 提示信息/错误信息)
    """
    try:
        # 替换命令为绝对路径（保留原有逻辑）
        command = replace_cmd_with_abs_path(command)
        # 执行命令（移除check=True，手动处理退出码）
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout  # 这里添加subprocess的超时控制
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # 关键修改2：区分不同场景
        if result.returncode == 0:
            # 场景1：命令执行成功（退出码0）
            if not stdout:
                # 子场景1.1：执行成功但无输出结果
                return True, "", get_msg("命令执行成功但未返回任何结果", "Command executed successfully but no results returned")
            # 子场景1.2：执行成功且有输出结果
            return True, stdout, get_msg("命令执行成功", "Command executed successfully")
        else:
            # 场景2：命令执行失败（非0退出码）
            # 特殊处理grep命令：退出码1表示无匹配结果，不算真正的执行失败
            cmd_lower = command.lower()
            if "grep" in cmd_lower and result.returncode == 1:
                return True, "", get_msg("未找到匹配内容", "No matching content found")

            # 真正的执行失败，合并错误信息
            error_msg = stderr or stdout or f"退出码：{result.returncode}"
            return False, "", get_msg(f"命令执行出错：{error_msg}", f"Command execution failed: {error_msg}")

    except Exception as e:
        # 场景3：其他异常（如命令不存在、权限问题等）
        return False, "", f"执行异常：{str(e)}"

# -------------------------- 远程命令执行 --------------------------

def get_remote_auth(host: str) -> Optional[Dict]:
    """保留你原有的远程认证信息获取函数"""
    remote_hosts = BaseConfig().get_config().public_config.remote_hosts
    for host_config in remote_hosts:
        if host in [host_config.host, host_config.name]:
            return {
                "host": host_config.host,
                "port": host_config.port,
                "username": host_config.username,
                "password": host_config.password,
            }
    return None


def ssh_exec_sync(host: str, command: str, timeout: int) -> Tuple[bool, str, str]:
    """
    SSH远程执行命令（修复阻塞问题+完善逻辑）
    :param host: 远程主机（IP/主机名）
    :param command: 待执行的命令
    :param timeout: 超时时间（秒）
    :return: (执行是否成功, 输出结果, 提示信息/错误信息)
    """
    # 1. 获取远程主机认证信息
    auth_config = get_remote_auth(host)
    if not auth_config:
        return False, "", get_msg(f"未找到远程主机{host}的认证配置", f"No auth config found for remote host {host}")

    # 2. 初始化SSH客户端
    ssh_client = paramiko.SSHClient()
    # 修复：添加主机密钥策略（必须）
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # 定义通道对象，用于后续超时控制
    channel = None

    try:
        # 连接远程主机（添加banner_timeout处理认证横幅）
        ssh_client.connect(
            hostname=auth_config["host"],
            port=auth_config.get("port", 22),
            username=auth_config["username"],
            password=auth_config["password"],
            timeout=timeout,  # 连接超时
            banner_timeout=timeout,  # 处理远程主机的认证横幅超时
            auth_timeout=timeout,    # 认证超时
            allow_agent=False,       # 禁用SSH代理（避免本地代理干扰）
            look_for_keys=False      # 禁用查找本地私钥（只使用密码认证）
        )

        # 3. 执行远程命令（改用invoke_shell，避免管道阻塞；或用exec_command+超时读取）
        # 方案1：使用exec_command + 非阻塞读取（推荐，更轻量）
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        channel = stdout.channel

        # 修复：设置通道超时，避免read阻塞
        channel.settimeout(timeout)

        # 读取输出（分块读取，避免阻塞）
        stdout_data = []
        stderr_data = []
        start_time = time.time()

        # 循环读取，直到通道关闭或超时
        while not channel.closed:
            # 检查是否超时
            if time.time() - start_time > timeout:
                channel.close()
                raise TimeoutError(f"Command execution timed out after {timeout} seconds")
            # 读取stdout
            if channel.recv_ready():
                stdout_data.append(channel.recv(1024).decode("utf-8", errors="ignore"))
            # 读取stderr
            if channel.recv_stderr_ready():
                stderr_data.append(channel.recv_stderr(1024).decode("utf-8", errors="ignore"))
            # 短暂休眠，减少CPU占用
            time.sleep(0.1)

        # 拼接输出数据
        stdout_data = "".join(stdout_data).strip()
        stderr_data = "".join(stderr_data).strip()
        # 获取退出码
        exit_code = channel.recv_exit_status()

        # 4. 处理执行结果
        if exit_code == 0:
            if not stdout_data:
                return True, "", get_msg("命令执行成功但未返回任何结果", "Command executed successfully but no results returned")
            return True, stdout_data, get_msg("命令执行成功", "Command executed successfully")
        else:
            # 处理grep特殊情况（退出码1表示无匹配）
            if "grep" in command.lower() and exit_code == 1:
                return True, "", get_msg("未找到匹配内容", "No matching content found")
            # 执行失败，拼接错误信息
            error_msg = stderr_data or stdout_data or f"退出码：{exit_code}"
            return False, "", get_msg(f"命令执行出错：{error_msg}", f"Command execution failed: {error_msg}")

    except paramiko.AuthenticationException:
        return False, "", get_msg(f"远程主机{host}认证失败", f"Authentication failed for remote host {host}")
    except paramiko.SSHException as e:
        return False, "", get_msg(f"SSH连接失败：{str(e)}", f"SSH connection failed: {str(e)}")
    except TimeoutError as e:
        return False, "", get_msg(f"命令执行超时：{str(e)}", f"Command execution timeout: {str(e)}")
    except Exception as e:
        return False, "", get_msg(f"远程执行异常：{str(e)}", f"Remote execution exception: {str(e)}")
    finally:
        # 确保SSH连接和通道关闭
        if channel and not channel.closed:
            channel.close()
        if ssh_client.get_transport() and ssh_client.get_transport().is_active():
            ssh_client.close()