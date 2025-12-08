from typing import Dict, Optional
from pydantic import Field
from config.public.base_config_loader import LanguageEnum
from servers.oe_cli_mcp_server.mcp_tools.base_tools.pkg_tool.base import (
    init_result_dict,
    PackageManager,
    PkgActionEnum,
    PkgCacheTypeEnum,
    parse_pkg_action,
    parse_cache_type,
    logger, lang
)

def pkg_tool(
        action: str = Field(
            ...,
            description="操作类型（枚举值：list/info/install/local-install/update/update-sec/remove/clean）"
        ),
        pkg_name: Optional[str] = Field(None, description="包名（info/install/update/remove必填）"),
        filter_key: Optional[str] = Field(None, description="包名过滤关键词（list操作可选）"),
        rpm_path: Optional[str] = Field(None, description="RPM文件路径（local-install必填）"),
        cache_type: str = Field(
            PkgCacheTypeEnum.ALL.value,
            description="缓存类型（枚举值：all/packages/metadata，clean操作默认all）"
        ),
        yes: bool = Field(True, description="自动确认（install/update/remove默认True）"),
) -> Dict:
    """
    OpenEuler软件包管理工具（枚举化参数，适配大模型识别）
    """
    # 初始化结果字典
    result = init_result_dict()
    result["pkg_name"] = pkg_name.strip() if pkg_name else ""
    pm = PackageManager(lang=lang)
    is_zh = lang == LanguageEnum.ZH

    # 1. 枚举值解析（兼容大模型字符串输入）
    try:
        action_enum = parse_pkg_action(action)
        cache_type_enum = parse_cache_type(cache_type)
    except ValueError as e:
        result["message"] = str(e) if is_zh else str(e)
        return result

    # 2. 核心参数校验
    try:
        if action_enum == PkgActionEnum.LIST:
            # 列出已安装包
            result["result"] = pm.list(filter_key=filter_key)
            result["success"] = True
            filter_desc = filter_key or "无" if is_zh else filter_key or "none"
            result["message"] = f"已安装包列表查询完成（过滤关键词：{filter_desc}）" if is_zh else f"Installed packages listed (filter: {filter_desc})"

        elif action_enum == PkgActionEnum.INFO:
            # 查询包详情
            if not pkg_name:
                raise ValueError("包名不能为空" if is_zh else "Package name cannot be empty")
            result["result"] = [pm.info(pkg_name.strip())]  # 统一列表格式
            result["success"] = True
            result["message"] = f"包{pkg_name}详情查询完成" if is_zh else f"Package {pkg_name} info queried"

        elif action_enum == PkgActionEnum.INSTALL:
            # 在线安装
            if not pkg_name:
                raise ValueError("包名不能为空" if is_zh else "Package name cannot be empty")
            log = pm.install(pkg_name.strip(), yes=yes)
            result["success"] = True
            result["message"] = f"包{pkg_name}在线安装成功" if is_zh else f"Package {pkg_name} installed successfully"
            result["result"] = log.splitlines()

        elif action_enum == PkgActionEnum.LOCAL_INSTALL:
            # 离线安装RPM
            if not rpm_path:
                raise ValueError("RPM路径不能为空" if is_zh else "RPM path cannot be empty")
            log = pm.local_install(rpm_path.strip(), yes=yes)
            result["success"] = True
            result["message"] = f"RPM包{rpm_path}安装成功" if is_zh else f"RPM package {rpm_path} installed successfully"
            result["result"] = log.splitlines()

        elif action_enum == PkgActionEnum.UPDATE:
            # 更新包
            log = pm.update(pkg_name=pkg_name.strip() if pkg_name else None, yes=yes)
            target = pkg_name or "所有包" if is_zh else pkg_name or "all packages"
            result["success"] = True
            result["message"] = f"{target}更新完成" if is_zh else f"{target} updated successfully"
            result["result"] = log.splitlines()

        elif action_enum == PkgActionEnum.UPDATE_SEC:
            # 仅更新安全补丁
            log = pm.update_sec(yes=yes)
            result["success"] = True
            result["message"] = "安全补丁更新完成" if is_zh else "Security patches updated successfully"
            result["result"] = log.splitlines()

        elif action_enum == PkgActionEnum.REMOVE:
            # 卸载包
            if not pkg_name:
                raise ValueError("包名不能为空" if is_zh else "Package name cannot be empty")
            log = pm.remove(pkg_name.strip(), yes=yes)
            result["success"] = True
            result["message"] = f"包{pkg_name}卸载完成" if is_zh else f"Package {pkg_name} removed successfully"
            result["result"] = log.splitlines()

        elif action_enum == PkgActionEnum.CLEAN:
            # 清理缓存
            log = pm.clean(cache_type=cache_type_enum)
            result["success"] = True
            result["message"] = f"{cache_type_enum.value}缓存清理完成" if is_zh else f"{cache_type_enum.value} cache cleaned successfully"
            result["result"] = log.splitlines()

    except Exception as e:
        result["message"] = f"操作失败：{str(e)}" if is_zh else f"Operation failed: {str(e)}"
        logger.error(f"Package manager error: {str(e)}")

    return result