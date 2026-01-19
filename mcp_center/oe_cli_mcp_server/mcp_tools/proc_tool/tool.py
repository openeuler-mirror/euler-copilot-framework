from typing import Dict, List, Optional
from pydantic import Field
from oe_cli_mcp_server.mcp_tools.proc_tool.base import (
    init_result_dict,
    ProcessManager,
    parse_proc_actions,
    is_zh,
    logger
)

def proc_tool(
        proc_actions: List[str] = Field(
            ...,
            description="进程操作列表（枚举值：list/find/stat/start/restart/stop/kill，支持多选）"
        ),
        proc_name: Optional[str] = Field(None, description="进程名称（find操作必填）"),
        pid: Optional[int] = Field(None, description="进程PID（find/stat/kill操作必填）"),
        service_name: Optional[str] = Field(None, description="服务名称（start/restart/stop操作必填）")
) -> Dict:
    """
    进程管理工具（支持查/启/停批量操作）
    语言配置从全局BaseConfig读取，不提供外部接口
    """
    # 初始化结果字典
    result = init_result_dict()
    proc_mgr = ProcessManager()
    use_zh = is_zh()

    # 解析操作类型列表
    try:
        parsed_actions = parse_proc_actions(proc_actions)
        result["proc_actions"] = [a.value for a in parsed_actions]
    except ValueError as e:
        result["message"] = str(e)
        return result

    # 执行批量操作
    try:
        batch_result = proc_mgr.exec_batch(
            actions=parsed_actions,
            proc_name=proc_name,
            pid=pid,
            service_name=service_name
        )
        result["result"] = batch_result
        result["success"] = True

        # 生成提示信息
        action_str = ",".join(result["proc_actions"])
        result["message"] = f"以下进程操作执行完成：{action_str}" if use_zh else f"Proc actions executed: {action_str}"

    except Exception as e:
        result["message"] = f"进程操作失败：{str(e)}" if use_zh else f"Proc action failed: {str(e)}"
        logger.error(f"Proc manager error: {str(e)}")

    return result