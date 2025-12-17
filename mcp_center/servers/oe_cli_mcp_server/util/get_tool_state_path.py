import os

from servers.oe_cli_mcp_server.util.get_project_root import get_project_root


def get_tool_state_path() -> str:
    """获取Tool状态持久化文件路径"""
    root = get_project_root()
    state_file = os.path.join(root, "data", "tool_state.json")
    # 确保目录存在
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    return state_file