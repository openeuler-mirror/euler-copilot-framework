import os

def get_project_root() -> str:
    """
    基于当前文件路径，向上查找项目根目录（默认找 .git 文件夹，可修改标志文件）
    :return: 项目根目录的绝对路径
    """
    # 获取当前脚本的绝对路径（__file__ 是当前文件的相对路径，abspath 转为绝对路径）
    current_path = os.path.abspath(__file__)

    # 向上递归查找，直到找到包含 .git 的目录（即项目根目录）
    while not os.path.exists(os.path.join(current_path, "mcp_config")):
        # 向上跳一级目录
        parent_path = os.path.dirname(current_path)
        # 防止递归到系统根目录（如 / 或 C:\）
        if parent_path == current_path:
            raise FileNotFoundError("未找到项目根目录（未发现 mcp_config 文件夹）")
        current_path = parent_path

    return current_path
