from typing import Dict, Optional

from config.public.base_config_loader import LanguageEnum

from oe_cli_mcp_server.mcp_tools.ssh_fix_tool.base import fix_sshd_issue


def ssh_fix_tool(
    target: Optional[str] = None,
    port: int = 22,
    lang: Optional[LanguageEnum] = LanguageEnum.ZH,
) -> Dict:
    """
    整合的SSH修复工具：解决SSH连接失败问题

    按顺序执行以下步骤：
    1. ping SSH端口检查连通性
    2. 检查sshd服务状态（systemctl status sshd）
    3. 修复/etc/ssh/sshd_config配置：
       - 确保Port 22已启用
       - 设置PermitRootLogin yes
       - 设置PasswordAuthentication yes
    4. 重启sshd服务（systemctl restart sshd）
    """
    return fix_sshd_issue(target, port=port)



