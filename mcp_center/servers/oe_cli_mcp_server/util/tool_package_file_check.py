import os


def tool_package_file_check(path: str) -> bool:
    """
    检查工具包文件是否存在
    :param path: 工具包文件路径
    :return: 是否存在
    """
    config_path = os.path.join(path, "config.json")
    tool_path = os.path.join(path, "tool.py")
    if not os.path.exists(config_path):
        return False
    if not os.path.exists(tool_path):
        return False
    return True
    