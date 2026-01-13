from typing import Dict, List
from pydantic import Field

from oe_cli_mcp_server.mcp_tools.sys_info_tool.base import (
    init_result_dict,
    SystemInfoCollector,
    parse_info_types,
    is_zh,
    logger
)

def sys_info_tool(
        info_types: List[str] = Field(
            ...,
            description="信息类型列表（枚举值可选：os/load/uptime/cpu/mem/disk/gpu/net/selinux/firewall，支持多选）"
        )
) -> Dict:
    """
    系统/硬件/安全信息采集工具（支持批量采集多类信息）
    语言配置从全局BaseConfig读取，不提供外部接口
    """
    # 初始化结果字典
    result = init_result_dict()
    collector = SystemInfoCollector()
    use_zh = is_zh()

    # 解析信息类型列表（字符串列表→枚举列表）
    try:
        parsed_info_types = parse_info_types(info_types)
        result["info_types"] = [t.value for t in parsed_info_types]  # 记录原始输入的类型列表
    except ValueError as e:
        result["message"] = str(e)
        return result

    # 批量采集信息
    try:
        batch_result = collector.collect_batch(parsed_info_types)
        result["result"] = batch_result
        result["success"] = True

        # 生成提示信息
        info_type_str = ",".join(result["info_types"])
        result["message"] = f"以下信息采集完成：{info_type_str}" if use_zh else f"Collected info types: {info_type_str}"

    except Exception as e:
        result["message"] = f"信息采集失败：{str(e)}" if use_zh else f"Info collection failed: {str(e)}"
        logger.error(f"System info batch collection error: {str(e)}")

    return result