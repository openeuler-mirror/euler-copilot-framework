import os

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
            return abs_path
    return cmd_name