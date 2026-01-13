from typing import Dict, Optional

from config.public.base_config_loader import LanguageEnum

from oe_cli_mcp_server.mcp_tools.network_tools.base import fix_network_bootproto_issue


def network_fix_bootproto_tool(
    target: Optional[str] = None,
    lang: Optional[LanguageEnum] = LanguageEnum.ZH,
) -> Dict:
    """
    网络自动修复工具：解决 NetworkManager 启动后未自动获取 IP 的问题。

    按照问题描述自动执行以下操作：
    1. 编辑 /etc/sysconfig/network-scripts/ifcfg-ens3
    2. 检查并修正 BOOTPROTO，确保为 \"dhcp\"（全小写）
    3. 重启 NetworkManager 服务：systemctl restart NetworkManager
    """
    # 目前语言仍由全局配置控制，此处保留 lang 以保持接口风格统一
    return fix_network_bootproto_issue(target=target)



