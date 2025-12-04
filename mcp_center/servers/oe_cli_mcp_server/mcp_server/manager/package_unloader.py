# mcp_server/manager/package_unloader.py
"""
包卸载器（纯卸载流程层）
核心职责：仅负责「包/分类级」卸载流程，最小操作单元为包
- 流程：查询包信息 → 清理函数关联 → 删除独立环境 → 调用仓库删除数据
- 设计原则：无状态、纯流程、依赖注入、结果导向
- 依赖：DepVenvManager（环境删除）、ToolRepository（数据查询/删除）
"""

import logging
from typing import Optional

from servers.oe_cli_mcp_server.mcp_server.dependency import DepVenvManager
from servers.oe_cli_mcp_server.mcp_server.manager.tool_repository import ToolRepository, tool_repository as default_repo

logger = logging.getLogger(__name__)

# 类型别名：与ToolRepository、PackageLoader保持一致
ToolType = str
PackageName = str


class PackageUnloader:
    """包卸载器：封装包/分类级卸载流程，不直接操作数据存储"""

    def __init__(self,
                 dep_manager: Optional[DepVenvManager] = None,
                 tool_repository: Optional[ToolRepository] = None):
        """
        初始化卸载器（依赖注入，便于测试和替换）
        :param dep_manager: 环境/依赖管理器（默认自动创建）
        :param tool_repository: 数据仓库（默认使用全局单例）
        """
        self._dep_manager = dep_manager or DepVenvManager()
        self._tool_repo = tool_repository or default_repo
        logger.info("PackageUnloader 初始化完成")

    # -------------------------------------------------------------------------
    # 公开API（对外暴露的卸载方法）
    # -------------------------------------------------------------------------
    def unload_package(self, package_name: PackageName, delete_env: bool = True) -> bool:
        """
        卸载单个包（核心流程）
        :param package_name: 要卸载的包名
        :param delete_env: 是否删除独立环境（默认True，全局环境不删除）
        :return: 卸载成功返回True，失败返回False
        """
        logger.info(f"[Package Unload Start] 包名：{package_name} | 删除环境：{delete_env}")

        # 1. 查询包信息（校验存在性+获取关联数据）
        package_info = self._tool_repo.get_package(package_name)
        if not package_info:
            logger.error(f"[Package Unload Failed] 包名：{package_name} | 原因：包不存在")
            return False

        venv_type = package_info["venv_type"]
        venv_path = package_info["venv_path"]
        tool_type = package_info["tool_type"]

        # 2. 条件删除独立环境（全局环境不删除）
        if delete_env and venv_type == "isolated":
            if not self._delete_isolated_env(package_name, venv_path):
                # 环境删除失败不中断包卸载，仅报警
                logger.warning(f"[Package Env Delete Failed] 包名：{package_name} | 环境路径：{venv_path}")

        # 3. 调用仓库删除包数据（连带函数/分类关联）
        if self._tool_repo.delete_package(package_name):
            logger.info(f"[Package Unload Success] 包名：{package_name} | 分类：{tool_type} | 环境类型：{venv_type}")
            return True
        else:
            logger.error(f"[Package Unload Failed] 包名：{package_name} | 原因：仓库删除失败")
            return False

    def unload_tool_type(self, tool_type: ToolType, delete_env: bool = True) -> bool:
        """
        卸载指定分类下所有包（批量卸载）
        :param tool_type: 分类名（支持字符串/Enum）
        :param delete_env: 是否删除独立环境（默认True）
        :return: 整体卸载成功返回True（所有包都卸载成功），部分失败返回False
        """
        # 标准化分类名（支持Enum类型）
        tool_type_str = self._normalize_tool_type(tool_type)
        logger.info(f"[ToolType Unload Start] 分类：{tool_type_str} | 删除环境：{delete_env}")

        # 1. 查询分类信息（校验存在性+获取下属包）
        type_info = self._tool_repo.get_tool_type(tool_type_str)
        if not type_info:
            logger.error(f"[ToolType Unload Failed] 分类：{tool_type_str} | 原因：分类不存在")
            return False

        package_names = type_info["package_names"]
        if not package_names:
            logger.info(f"[ToolType Unload Completed] 分类：{tool_type_str} | 原因：无下属包")
            return True

        # 2. 批量卸载下属包
        unload_results = []
        for pkg_name in package_names:
            result = self.unload_package(pkg_name, delete_env)
            unload_results.append(result)
            if not result:
                logger.error(f"[ToolType Unload Package Failed] 分类：{tool_type_str} | 包名：{pkg_name}")

        # 3. 校验整体结果（所有包都卸载成功才返回True）
        all_success = all(unload_results)
        logger.info(
            f"[ToolType Unload Completed] 分类：{tool_type_str} | "
            f"处理包数：{len(package_names)} | "
            f"成功数：{sum(unload_results)} | "
            f"失败数：{len(unload_results) - sum(unload_results)} | "
            f"整体成功：{all_success}"
        )
        return all_success

    # -------------------------------------------------------------------------
    # 内部辅助方法（私有，单一职责）
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_tool_type(tool_type: ToolType) -> str:
        """标准化分类名（支持Enum类型）"""
        return tool_type.value if hasattr(tool_type, "value") else str(tool_type)

    def _delete_isolated_env(self, package_name: PackageName, venv_path: str) -> bool:
        """删除包的独立环境（封装环境管理器调用）"""
        try:
            # 调用环境管理器删除独立环境（包名为环境标识）
            delete_success = self._dep_manager.delete_isolated_venv(tool_id=package_name)
            if delete_success:
                logger.debug(f"[Isolated Env Deleted] 包名：{package_name} | 环境路径：{venv_path}")
            return delete_success
        except Exception as e:
            logger.error(
                f"[Isolated Env Delete Failed] 包名：{package_name} | 环境路径：{venv_path} | 原因：{str(e)}",
                exc_info=True
            )
            return False


# 单例实例（默认使用全局依赖和仓库）
package_unloader = PackageUnloader()