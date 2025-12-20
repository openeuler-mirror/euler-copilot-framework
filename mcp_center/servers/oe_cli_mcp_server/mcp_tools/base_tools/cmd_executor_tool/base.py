import logging
import os
import shlex
from config.public.base_config_loader import BaseConfig

lang = BaseConfig().get_config().public_config.language

logger = logging.getLogger("cmd_executor_tool")
logger.setLevel(logging.INFO)

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

