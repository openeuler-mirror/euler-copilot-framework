# mcp_server/manager/manager.py
"""
Tool 全局管理器（对外统一API层）
核心职责：封装内部组件，对外提供简洁、统一的Tool操作API
- 角色：协调者（不包含业务逻辑，仅转发调用+参数校验）
- 设计原则：对外透明、API语义化、兼容原有使用习惯、屏蔽内部实现
- 依赖：PackageLoader（加载）、PackageUnloader（卸载）、ToolRepository（查询）
"""
import json
import logging
import os
from typing import Dict, List, Optional, Any
from servers.oe_cli_mcp_server.mcp_server.manager.tool_repository import ToolRepository, tool_repository as default_repo
from servers.oe_cli_mcp_server.mcp_server.manager.package_loader import PackageLoader, package_loader as default_loader
from servers.oe_cli_mcp_server.mcp_server.manager.package_unloader import PackageUnloader, package_unloader as default_unloader

from servers.oe_cli_mcp_server.util.get_tool_state_path import get_tool_state_path

logger = logging.getLogger(__name__)

# 类型别名：与内部组件保持一致，提升API可读性
ToolType = str
PackageName = str
PackageDir = str
FuncName = str


class ToolManager:
    """Tool全局管理器：对外提供加载/卸载/查询一站式API"""

    def __init__(self,
                 tool_repository: Optional[ToolRepository] = None,
                 package_loader: Optional[PackageLoader] = None,
                 package_unloader: Optional[PackageUnloader] = None):
        """
        初始化管理器（依赖注入，便于测试和组件替换）
        :param tool_repository: 数据仓库组件（默认使用全局单例）
        :param package_loader: 包加载器组件（默认使用全局单例）
        :param package_unloader: 包卸载器组件（默认使用全局单例）
        """
        self._repo = tool_repository or default_repo
        self._loader = package_loader or default_loader
        self._unloader = package_unloader or default_unloader
        self._state_file_path = get_tool_state_path()
        logger.info("ToolManager 初始化完成 | 内部组件已就绪")

    # -------------------------------------------------------------------------
    # 加载操作API（转发给PackageLoader）
    # -------------------------------------------------------------------------
    def load_package(self, package_dir: PackageDir) -> Optional[PackageName]:
        """
        加载单个包（最小操作单元）
        :param package_dir: 包目录绝对路径
        :return: 成功返回包名，失败返回None
        """
        if not package_dir:
            logger.error("[Load Package Failed] 原因：包目录不能为空")
            return None
        result = self._loader.load_package(package_dir)
        if result:
            self.persist_tool_state()
        return result

    def load_tool_type(self, tool_type: ToolType) -> Dict[str, Any]:
        """
        加载指定分类下所有包（批量加载）
        :param tool_type: 分类名（支持字符串/Enum）
        :return: 加载结果统计（总包数/成功数/失败数等）
        """
        if not tool_type:
            logger.error("[Load ToolType Failed] 原因：分类名不能为空")
            return self._init_empty_result("分类名不能为空")
        result = self._loader.load_tool_type(tool_type)
        self.persist_tool_state()
        return result

    # -------------------------------------------------------------------------
    # 卸载操作API（转发给PackageUnloader）
    # -------------------------------------------------------------------------
    def unload_package(self, package_name: PackageName, delete_env: bool = True) -> bool:
        """
        卸载单个包（最小操作单元）
        :param package_name: 要卸载的包名
        :param delete_env: 是否删除独立环境（默认True，全局环境不删除）
        :return: 卸载成功返回True，失败返回False
        """
        if not package_name:
            logger.error("[Unload Package Failed] 原因：包名不能为空")
            return False
        result = self._unloader.unload_package(package_name, delete_env)
        if result:
            self.persist_tool_state()
        return result

    def unload_tool_type(self, tool_type: ToolType, delete_env: bool = True) -> bool:
        """
        卸载指定分类下所有包（批量卸载）
        :param tool_type: 分类名（支持字符串/Enum）
        :param delete_env: 是否删除独立环境（默认True）
        :return: 整体卸载成功返回True（所有包都卸载成功），部分失败返回False
        """
        if not tool_type:
            logger.error("[Unload ToolType Failed] 原因：分类名不能为空")
            return False

        result = self._unloader.unload_tool_type(tool_type, delete_env)
        if result:
            self.persist_tool_state()
        return result

    # -------------------------------------------------------------------------
    # 查询操作API（转发给ToolRepository）
    # -------------------------------------------------------------------------
    def get_package_info(self, package_name: PackageName) -> Optional[Dict[str, Any]]:
        """
        查询包完整信息（含环境、函数列表等）
        :param package_name: 包名
        :return: 包信息字典，包不存在返回None
        """
        if not package_name:
            logger.error("[Get Package Info Failed] 原因：包名不能为空")
            return None
        return self._repo.get_package(package_name)

    def get_func_info(self, func_name: FuncName) -> Optional[Dict[str, Any]]:
        """
        查询函数详情（含所属包/分类/环境等关联信息）
        :param func_name: 函数名（全局唯一）
        :return: 函数信息字典，函数不存在返回None
        """
        if not func_name:
            logger.error("[Get Func Info Failed] 原因：函数名不能为空")
            return None
        return self._repo.get_func(func_name)

    def get_tool_type_info(self, tool_type: ToolType) -> Optional[Dict[str, Any]]:
        """
        查询分类详情（含下属包列表、统计信息等）
        :param tool_type: 分类名
        :return: 分类信息字典，分类不存在返回None
        """
        if not tool_type:
            logger.error("[Get ToolType Info Failed] 原因：分类名不能为空")
            return None
        return self._repo.get_tool_type(tool_type)

    # -------------------------------------------------------------------------
    # 列表查询API（转发给ToolRepository）
    # -------------------------------------------------------------------------
    def list_packages(self, tool_type: Optional[ToolType] = None) -> List[PackageName]:
        """
        列出所有包名（可选按分类过滤）
        :param tool_type: 分类名（None表示列出所有包）
        :return: 包名列表（按添加时间升序排列）
        """
        return self._repo.list_packages(tool_type)

    def list_funcs(self, package_name: Optional[PackageName] = None) -> List[FuncName]:
        """
        列出所有函数名（可选按包过滤）
        :param package_name: 包名（None表示列出所有函数）
        :return: 函数名列表
        """
        return self._repo.list_funcs(package_name)

    def list_tool_types(self) -> List[ToolType]:
        """列出所有已注册的分类名"""
        return self._repo.list_tool_types()

    # -------------------------------------------------------------------------
    # 持久化相关API（转发给ToolRepository）
    # -------------------------------------------------------------------------
    def get_serializable_data(self) -> Dict[str, Any]:
        """获取可序列化数据（用于持久化存储）"""
        data = self._repo.get_serializable_data()
        logger.debug(f"[Serializable Data Got] 包数：{len(data.get('serializable_packages', {}))}")
        return data

    def get_package_path(self,package_name):
        data = self._repo.get_serializable_data()
        packages_info = data.get('serializable_packages', {})
        return packages_info[package_name]["package_dir"]

    def load_serializable_data(self, data: Dict[str, Any]) -> Dict[str, int]:
        """
        加载序列化数据（用于重启后恢复关联关系）
        :param data: 序列化数据（来自持久化文件）
        :return: 恢复结果统计
        """
        if not isinstance(data, dict):
            logger.error("[Load Serializable Data Failed] 原因：数据格式必须是字典")
            return {"total_package": 0, "success_package": 0, "fail_package": 0}
        return self._repo.load_serializable_data(data)

    def reload_package_functions(self) -> Dict[str, Any]:
        """
        重新导入所有已加载包的函数对象（持久化恢复后必须执行）
        逻辑：从 ToolRepository 获取包目录 → 用 PackageLoader 重新导入函数 → 更新到仓库
        :return: 重新导入结果统计
        """
        result = {
            "total_package": 0,
            "success_package": 0,
            "fail_package": [],
            "total_func": 0
        }

        # 1. 从仓库获取所有已恢复元信息的包
        package_names = self.list_packages()
        result["total_package"] = len(package_names)
        if result["total_package"] == 0:
            logger.info("[Reload Functions] 无已加载的包，跳过重新导入")
            return result

        # 2. 逐个包重新导入函数
        for pkg_name in package_names:
            pkg_info = self.get_package_info(pkg_name)
            if not pkg_info or not pkg_info.get("package_dir"):
                logger.error(f"[Reload Functions Failed] 包 {pkg_name} 无有效目录信息")
                result["fail_package"].append(pkg_name)
                continue

            try:
                # 关键：调用 load_package 重新导入（依赖 PackageLoader 内部兼容“已存在包”）
                loaded_pkg_name = self.load_package(pkg_info["package_dir"])

                if loaded_pkg_name:
                    # 重新导入成功：统计包数和函数数
                    result["success_package"] += 1
                    # 获取该包重新导入后的函数数，更新统计
                    funcs = self.list_funcs(pkg_name)
                    result["total_func"] += len(funcs)
                    logger.info(f"[Reload Functions Success] 包 {pkg_name}：{len(funcs)} 个函数")
                else:
                    # load_package 返回 None：可能是包已存在但函数导入失败，或其他错误
                    logger.warning(f"[Reload Functions Warning] 包 {pkg_name} 未成功重新导入")
                    result["fail_package"].append(pkg_name)
            except Exception as e:
                logger.error(f"[Reload Functions Failed] 包 {pkg_name}：{str(e)}", exc_info=True)
                result["fail_package"].append(pkg_name)

        # 补充日志：明确最终结果
        logger.info(
            f"[Reload Functions Done] 总包数：{result['total_package']} | "
            f"成功：{result['success_package']} | 失败：{len(result['fail_package'])} | "
            f"总函数数：{result['total_func']}"
        )
        return result

    # -------------------------------------------------------------------------
    # 持久化核心API（对外暴露，支持手动触发）
    # -------------------------------------------------------------------------
    def persist_tool_state(self) -> bool:
        """
        持久化Tool状态（将内存中的三级关联数据写入文件）
        :return: 持久化成功返回True，失败返回False
        """
        try:
            # 1. 从仓库获取可序列化数据
            serializable_data = self._repo.get_serializable_data()
            # 2. 写入文件（保证原子性：先写临时文件，再替换目标文件）
            temp_file = f"{self._state_file_path}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            # 3. 替换目标文件（避免写入过程中断导致文件损坏）
            os.replace(temp_file, self._state_file_path)
            logger.info(f"[Tool State Persisted] 成功写入持久化文件 | 包数：{len(serializable_data.get('serializable_packages', {}))}")
            return True
        except Exception as e:
            logger.error(f"[Tool State Persist Failed] 原因：{str(e)}", exc_info=True)
            # 清理临时文件
            if os.path.exists(f"{self._state_file_path}.tmp"):
                os.remove(f"{self._state_file_path}.tmp")
            return False

    def restore_tool_state(self) -> Dict[str, int]:
        """
        恢复Tool状态（从持久化文件加载数据到内存）
        :return: 恢复结果统计（总包数/成功数/失败数）
        """
        # 1. 校验文件是否存在
        if not os.path.exists(self._state_file_path):
            logger.warning(f"[Tool State Restore Failed] 原因：持久化文件不存在 - {self._state_file_path}")
            return {"total_package": 0, "success_package": 0, "fail_package": 0}
        try:
            # 2. 读取文件数据
            with open(self._state_file_path, "r", encoding="utf-8") as f:
                serializable_data = json.load(f)
            # 3. 调用仓库加载数据到内存
            result = self._repo.load_serializable_data(serializable_data)
            logger.info(f"[Tool State Restored] 从持久化文件恢复 | 结果：{result}")
            return result
        except json.JSONDecodeError:
            logger.error(f"[Tool State Restore Failed] 原因：持久化文件格式错误 - {self._state_file_path}")
            # 可选：备份损坏的文件
            if os.path.exists(self._state_file_path):
                backup_file = f"{self._state_file_path}.corrupt.{os.path.getmtime(self._state_file_path)}"
                os.rename(self._state_file_path, backup_file)
                logger.info(f"[Corrupt File Backed Up] 备份路径：{backup_file}")
            return {"total_package": 0, "success_package": 0, "fail_package": 0}
        except Exception as e:
            logger.error(f"[Tool State Restore Failed] 原因：{str(e)}", exc_info=True)
            return {"total_package": 0, "success_package": 0, "fail_package": 0}

    # -------------------------------------------------------------------------
    # 内部辅助方法（私有，单一职责）
    # -------------------------------------------------------------------------
    @staticmethod
    def _init_empty_result(fail_reason: str) -> Dict[str, Any]:
        """初始化空的加载结果统计"""
        return {
            "tool_type": "",
            "total_package": 0,
            "success_package": 0,
            "fail_package": [],
            "success_func": 0,
            "fail_reason": fail_reason
        }


# 全局单例实例（对外暴露的唯一入口，保持原有使用习惯）
tool_manager = ToolManager()
