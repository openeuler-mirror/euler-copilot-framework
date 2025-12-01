# mcp_server/manager/tool_repository.py
"""
Tool 数据仓库（纯数据操作层）
核心职责：维护「分类→包→函数」三级关联数据，提供原子化增删改查方法
- 核心操作单元：包（函数为包的附属资源，不支持单独操作）
- 设计原则：纯数据处理、无业务逻辑、强数据一致性、API语义化
- 数据隔离：对外暴露数据均为深拷贝，避免外部修改内部状态
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)

# 类型别名：提升代码可读性与类型一致性
ToolType = str
PackageName = str
PackageDir = str
FuncName = str
FuncDetail = Dict[str, Any]  # 格式：{"func": callable, "description": str}


class ToolRepository:
    """Tool数据仓库：封装三级关联数据的原子操作，确保数据一致性"""

    def __init__(self):
        """初始化内存存储结构（三级关联，仅内存持有）"""
        # 1. 包核心存储：key=包名，value=包完整信息（含函数详情）
        self._packages: Dict[PackageName, Dict[str, Any]] = {}
        # 2. 分类-包映射：key=分类名，value=包名列表（优化分类查询性能）
        self._type_package_map: Dict[ToolType, List[PackageName]] = {}
        # 3. 函数-包映射：key=函数名，value=包名（快速反向查询函数所属包）
        self._func_package_map: Dict[FuncName, PackageName] = {}

    # -------------------------------------------------------------------------
    # 包级核心操作（核心API：添加/删除/查询/列表）
    # -------------------------------------------------------------------------
    def add_package(self,
                   package_name: PackageName,
                   tool_type: ToolType,
                   package_dir: PackageDir,
                   venv_path: str,
                   venv_type: str,
                   funcs: Dict[FuncName, FuncDetail]) -> bool:
        """
        原子化添加包（含下属函数），确保三级关联数据同步更新
        :param package_name: 包名（全局唯一）
        :param tool_type: 所属分类（如 base/docker）
        :param package_dir: 包目录绝对路径
        :param venv_path: 包关联的虚拟环境路径
        :param venv_type: 环境类型（global/isolated）
        :param funcs: 包内函数详情字典（key=函数名，value=FuncDetail）
        :return: 添加成功返回True，失败返回False
        """
        # 1. 前置参数校验（避免无效数据入库）
        if not self._validate_add_package_params(package_name, tool_type, package_dir, venv_path, venv_type, funcs):
            return False

        # 2. 原子化添加（所有关联操作要么全成功，要么全回滚）
        try:
            # 2.1 存储包完整信息（深拷贝避免外部修改影响内部状态）
            self._packages[package_name] = {
                "package_name": package_name,
                "tool_type": tool_type,
                "package_dir": package_dir,
                "venv_path": venv_path,
                "venv_type": venv_type,
                "funcs": deepcopy(funcs),
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # 2.2 更新分类-包关联映射
            self._add_to_type_package_map(tool_type, package_name)

            # 2.3 更新函数-包关联映射
            self._add_to_func_package_map(funcs.keys(), package_name)

            logger.info(
                f"[Package Added] 包名：{package_name} | 分类：{tool_type} | 函数数：{len(funcs)} | 环境类型：{venv_type}"
            )
            return True
        except Exception as e:
            logger.error(f"[Package Add Failed] 包名：{package_name} | 原因：{str(e)}", exc_info=True)
            self._rollback_add_package(package_name, tool_type, funcs.keys())
            return False

    def delete_package(self, package_name: PackageName) -> bool:
        """
        原子化删除包（连带删除下属函数、分类关联）
        :param package_name: 要删除的包名
        :return: 删除成功返回True，失败返回False
        """
        # 1. 校验包是否存在
        if package_name not in self._packages:
            logger.warning(f"[Package Delete Failed] 包名：{package_name} | 原因：包不存在")
            return False

        # 2. 缓存关联数据（用于后续清理映射）
        package = self._packages[package_name]
        tool_type = package["tool_type"]
        func_names = list(package["funcs"].keys())

        # 3. 原子化删除操作
        try:
            # 3.1 删除包核心数据
            del self._packages[package_name]

            # 3.2 清理分类-包关联（空分类自动删除）
            self._remove_from_type_package_map(tool_type, package_name)

            # 3.3 清理函数-包关联
            self._remove_from_func_package_map(func_names)

            logger.info(
                f"[Package Deleted] 包名：{package_name} | 分类：{tool_type} | 连带删除函数数：{len(func_names)}"
            )
            return True
        except Exception as e:
            logger.error(f"[Package Delete Failed] 包名：{package_name} | 原因：{str(e)}", exc_info=True)
            return False

    def get_package(self, package_name: PackageName) -> Optional[Dict[str, Any]]:
        """
        查询包完整信息（含下属函数），返回深拷贝避免外部修改
        :param package_name: 包名
        :return: 包完整信息字典，包不存在返回None
        """
        package = self._packages.get(package_name)
        return deepcopy(package) if package else None

    def list_packages(self, tool_type: Optional[ToolType] = None) -> List[PackageName]:
        """
        列出包名列表（可选按分类过滤），按添加时间升序排列
        :param tool_type: 分类名（None表示列出所有包）
        :return: 包名列表（拷贝版，避免外部修改）
        """
        if tool_type:
            # 按分类过滤，返回拷贝避免外部修改内部列表
            return self._type_package_map.get(tool_type, []).copy()
        # 列出所有包，按创建时间升序排序
        return sorted(
            self._packages.keys(),
            key=lambda pkg_name: self._packages[pkg_name]["create_time"]
        )

    # -------------------------------------------------------------------------
    # 函数级查询操作（附属API：仅查询，无添加/删除）
    # -------------------------------------------------------------------------
    def get_func(self, func_name: FuncName) -> Optional[Dict[str, Any]]:
        """
        查询函数详情（含所属包/分类信息）
        :param func_name: 函数名（全局唯一）
        :return: 函数详情字典，函数不存在返回None
        """
        # 1. 快速定位所属包
        package_name = self._func_package_map.get(func_name)
        if not package_name:
            logger.debug(f"[Func Query Failed] 函数名：{func_name} | 原因：函数不存在")
            return None

        # 2. 校验数据一致性（避免映射失效导致的脏数据）
        package = self._packages.get(package_name)
        if not package or func_name not in package["funcs"]:
            logger.warning(f"[Data Inconsistent] 函数名：{func_name} | 原因：函数-包映射失效，已清理")
            self._remove_from_func_package_map([func_name])
            return None

        # 3. 组装函数完整信息（含关联的包/分类信息）
        func_detail = package["funcs"][func_name]
        return deepcopy({
            "func_name": func_name,
            "func": func_detail["func"],
            "description": func_detail["description"],
            "package_name": package_name,
            "tool_type": package["tool_type"],
            "package_dir": package["package_dir"],
            "venv_path": package["venv_path"],
            "venv_type": package["venv_type"]
        })

    def list_funcs(self, package_name: Optional[PackageName] = None) -> List[FuncName]:
        """
        列出函数名列表（可选按包过滤）
        :param package_name: 包名（None表示列出所有函数）
        :return: 函数名列表（拷贝版）
        """
        if package_name:
            package = self._packages.get(package_name)
            return list(package["funcs"].keys()) if package else []
        # 列出所有函数，按所属包的创建时间排序
        sorted_packages = self.list_packages()
        all_funcs = []
        for pkg_name in sorted_packages:
            pkg_funcs = list(self._packages[pkg_name]["funcs"].keys())
            all_funcs.extend(pkg_funcs)
        return all_funcs

    # -------------------------------------------------------------------------
    # 分类级操作（聚合API：查询/删除）
    # -------------------------------------------------------------------------
    def get_tool_type(self, tool_type: ToolType) -> Optional[Dict[str, Any]]:
        """
        查询分类详情（含下属包列表、统计信息）
        :param tool_type: 分类名
        :return: 分类详情字典，分类不存在返回None
        """
        package_names = self._type_package_map.get(tool_type)
        if not package_names:
            logger.debug(f"[ToolType Query Failed] 分类名：{tool_type} | 原因：分类不存在")
            return None

        # 统计分类下的有效包数和函数总数
        valid_packages = [pkg_name for pkg_name in package_names if pkg_name in self._packages]
        total_funcs = 0
        for pkg_name in valid_packages:
            total_funcs += len(self._packages[pkg_name]["funcs"])

        return {
            "tool_type": tool_type,
            "package_names": valid_packages.copy(),
            "total_package": len(valid_packages),
            "total_func": total_funcs
        }

    def list_tool_types(self) -> List[ToolType]:
        """列出所有已注册的分类名"""
        return list(self._type_package_map.keys())

    def delete_tool_type(self, tool_type: ToolType) -> bool:
        """
        原子化删除分类（连带删除下属所有包）
        :param tool_type: 分类名
        :return: 整体删除成功返回True，部分失败返回False
        """
        # 1. 校验分类是否存在
        if tool_type not in self._type_package_map:
            logger.warning(f"[ToolType Delete Failed] 分类名：{tool_type} | 原因：分类不存在")
            return False

        # 2. 缓存分类下所有包（避免删除过程中映射变化）
        package_names = self._type_package_map[tool_type].copy()
        if not package_names:
            logger.info(f"[ToolType Delete] 分类名：{tool_type} | 无下属包，直接删除分类")
            del self._type_package_map[tool_type]
            return True

        # 3. 批量删除下属包
        delete_results = [self.delete_package(pkg_name) for pkg_name in package_names]
        all_success = all(delete_results)

        logger.info(
            f"[ToolType Delete Completed] 分类名：{tool_type} | 处理包数：{len(package_names)} | 全部成功：{all_success}"
        )
        return all_success

    # -------------------------------------------------------------------------
    # 序列化/反序列化（用于持久化与重启恢复）
    # -------------------------------------------------------------------------
    def get_serializable_data(self) -> Dict[str, Any]:
        """
        获取可序列化的数据（用于持久化）
        说明：剔除不可序列化的函数对象，仅保留元信息
        """
        serializable_packages = {}

        for pkg_name, pkg_info in self._packages.items():
            serializable_packages[pkg_name] = {
                "package_name": pkg_name,
                "tool_type": pkg_info["tool_type"],
                "package_dir": pkg_info["package_dir"],
                "venv_path": pkg_info["venv_path"],
                "venv_type": pkg_info["venv_type"],
                "func_names": list(pkg_info["funcs"].keys()),
                "create_time": pkg_info["create_time"]
            }

        return {
            "serializable_packages": serializable_packages,
            "type_package_map": self._type_package_map.copy(),
            "func_package_map": self._func_package_map.copy(),
            "serialize_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def load_serializable_data(self, data: Dict[str, Any]) -> Dict[str, int]:
        """
        加载序列化数据（用于重启后恢复关联关系）
        说明：仅恢复元信息和关联映射，函数对象需通过PackageLoader重新导入
        :param data: 序列化数据（来自持久化文件）
        :return: 恢复结果统计（成功/失败包数）
        """
        result = {
            "total_package": 0,
            "success_package": 0,
            "fail_package": 0
        }

        try:
            serializable_packages = data.get("serializable_packages", {})
            type_package_map = data.get("type_package_map", {})
            func_package_map = data.get("func_package_map", {})

            result["total_package"] = len(serializable_packages)

            # 恢复包元信息（无函数对象）
            for pkg_name, pkg_meta in serializable_packages.items():
                self._packages[pkg_name] = {
                    "package_name": pkg_name,
                    "tool_type": pkg_meta["tool_type"],
                    "package_dir": pkg_meta["package_dir"],
                    "venv_path": pkg_meta["venv_path"],
                    "venv_type": pkg_meta["venv_type"],
                    "funcs": {},  # 函数对象后续通过加载包补充
                    "create_time": pkg_meta["create_time"]
                }
                result["success_package"] += 1

            # 恢复分类-包映射
            self._type_package_map = deepcopy(type_package_map)

            # 恢复函数-包映射
            self._func_package_map = deepcopy(func_package_map)

            result["fail_package"] = result["total_package"] - result["success_package"]
            logger.info(
                f"[Serializable Data Loaded] 总包数：{result['total_package']} | "
                f"成功恢复：{result['success_package']} | 失败：{result['fail_package']}"
            )
            return result
        except Exception as e:
            logger.error(f"[Serializable Data Load Failed] 原因：{str(e)}", exc_info=True)
            # 异常时清空已恢复数据，避免脏数据
            self._reset_all_data()
            return result

    def update_package_functions(self, package_name: str, funcs: Dict[str, callable]):
        """
        更新包的函数对象（持久化恢复后补充）
        :param package_name: 包名
        :param funcs: 函数名→函数对象的映射
        """
        if package_name not in self._packages:
            raise ValueError(f"包 {package_name} 不存在于仓库中")
        # 更新包的函数对象（覆盖原有空的 funcs）
        self._packages[package_name]["funcs"] = funcs
        # 同步更新函数-包映射（确保 get_func 能找到函数）
        for func_name in funcs.keys():
            self._func_package_map[func_name] = package_name

    # -------------------------------------------------------------------------
    # 内部辅助方法（私有，不对外暴露）
    # -------------------------------------------------------------------------
    def _validate_add_package_params(self,
                                    package_name: PackageName,
                                    tool_type: ToolType,
                                    package_dir: PackageDir,
                                    venv_path: str,
                                    venv_type: str,
                                    funcs: Dict[FuncName, FuncDetail]) -> bool:
        """校验添加包的参数合法性"""
        # 1. 非空校验
        if not all([package_name, tool_type, package_dir, venv_path, venv_type]):
            logger.error(f"[Param Invalid] 包名：{package_name} | 原因：必填参数不能为空")
            return False

        # 2. 包名唯一性校验
        if package_name in self._packages:
            logger.warning(f"[Param Invalid] 包名：{package_name} | 原因：包名已存在")
            #return False

        # 3. 环境类型合法性校验
        if venv_type not in ["global", "isolated"]:
            logger.error(f"[Param Invalid] 包名：{package_name} | 原因：环境类型必须是 global/isolated")
            return False

        # 4. 函数参数校验
        if not isinstance(funcs, dict) or len(funcs) == 0:
            logger.error(f"[Param Invalid] 包名：{package_name} | 原因：函数列表不能为空字典")
            return False

        # 5. 函数名唯一性校验（全局唯一）
        duplicate_funcs = [func_name for func_name in funcs if func_name in self._func_package_map]
        if duplicate_funcs:
            logger.warning(f"[Param Invalid] 包名：{package_name} | 原因：函数名重复 - {duplicate_funcs}")
            #return False

        # 6. 函数详情格式校验
        for func_name, func_detail in funcs.items():
            if not isinstance(func_detail, dict) or "func" not in func_detail or "description" not in func_detail:
                logger.error(f"[Param Invalid] 包名：{package_name} | 原因：函数[{func_name}]格式错误（需包含func和description）")
                return False
            if not callable(func_detail["func"]):
                logger.error(f"[Param Invalid] 包名：{package_name} | 原因：函数[{func_name}]必须是可调用对象")
                return False

        return True

    def _add_to_type_package_map(self, tool_type: ToolType, package_name: PackageName) -> None:
        """添加分类-包关联"""
        if tool_type not in self._type_package_map:
            self._type_package_map[tool_type] = []
        if package_name not in self._type_package_map[tool_type]:
            self._type_package_map[tool_type].append(package_name)

    def _remove_from_type_package_map(self, tool_type: ToolType, package_name: PackageName) -> None:
        """移除分类-包关联（空分类自动删除）"""
        if tool_type not in self._type_package_map:
            return
        if package_name in self._type_package_map[tool_type]:
            self._type_package_map[tool_type].remove(package_name)
        # 空分类自动清理
        if not self._type_package_map[tool_type]:
            del self._type_package_map[tool_type]
            logger.debug(f"[ToolType Cleaned] 分类名：{tool_type} | 原因：无下属包")

    def _add_to_func_package_map(self, func_names: List[FuncName], package_name: PackageName) -> None:
        """添加函数-包关联"""
        for func_name in func_names:
            self._func_package_map[func_name] = package_name

    def _remove_from_func_package_map(self, func_names: List[FuncName]) -> None:
        """移除函数-包关联"""
        for func_name in func_names:
            if func_name in self._func_package_map:
                del self._func_package_map[func_name]

    def _rollback_add_package(self,
                             package_name: PackageName,
                             tool_type: ToolType,
                             func_names: List[FuncName]) -> None:
        """添加包失败时回滚数据，确保数据一致性"""
        logger.debug(f"[Add Package Rollback] 包名：{package_name} | 开始回滚数据")
        # 回滚包数据
        if package_name in self._packages:
            del self._packages[package_name]
        # 回滚分类-包关联
        self._remove_from_type_package_map(tool_type, package_name)
        # 回滚函数-包关联
        self._remove_from_func_package_map(func_names)
        logger.debug(f"[Add Package Rollback] 包名：{package_name} | 回滚完成")

    def _reset_all_data(self) -> None:
        """重置所有数据（异常恢复时使用）"""
        self._packages.clear()
        self._type_package_map.clear()
        self._func_package_map.clear()
        logger.warning("[Data Reset] 所有存储数据已清空")


# 单例实例（全局共享一个数据仓库，确保数据一致性）
tool_repository = ToolRepository()