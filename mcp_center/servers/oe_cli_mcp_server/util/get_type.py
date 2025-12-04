from mcp_tools.tool_type import ToolType


def get_type(package : str):
    type_map = {
        "base_tools" : ToolType.BASE,
        "personal_tools" : ToolType.BASE,
        "AI_tools" : ToolType.BASE,
        "mirror_tools" : ToolType.BASE,
        "cal_tools" : ToolType.BASE
    }
    if not package in type_map:
        return ToolType.BASE
    return type_map[package]