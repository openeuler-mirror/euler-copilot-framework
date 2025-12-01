# mcp_server/manager/package_loader.py
"""
包加载器（纯加载流程层）
核心职责：仅负责「包/分类级」加载流程，最小操作单元为包
- 流程：校验包合法性 → 准备环境 → 安装依赖 → 导入模块 → 校验函数 → 调用仓库存储
- 设计原则：无状态、纯流程、依赖注入、结果导向
- 依赖：DepVenvManager（环境/依赖管理）、ToolRepository（数据存储）
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from importlib.util import spec_from_file_location, module_from_spec

from mcp_server.dependency import DepVenvManager
from util.get_project_root import get_project_root
from util.tool_package_file_check import tool_package_file_check
from mcp_server.manager.tool_repository import ToolRepository, tool_repository as default_repo

logger = logging.getLogger(__name__)

# 类型别名：与ToolRepository保持一致
ToolType = str
PackageName = str
PackageDir = str
FuncName = str
FuncDetail = Dict[str, Any]


class PackageLoader:
    """包加载器：封装包/分类级加载流程，不直接操作数据存储"""

    def __init__(self,
                 dep_manager: Optional[DepVenvManager] = None,
                 tool_repository: Optional[ToolRepository] = None):
        """
        初始化加载器（依赖注入，便于测试和替换）
        :param dep_manager: 环境/依赖管理器（默认自动创建）
        :param tool_repository: 数据仓库（默认使用全局单例）
        """
        self._dep_manager = dep_manager or DepVenvManager()
        self._tool_repo = tool_repository or default_repo
        # 初始化全局环境（确保全局虚拟环境存在）
        self._dep_manager.create_global_venv()
        logger.info("PackageLoader 初始化完成 | 全局虚拟环境已就绪")

    # -------------------------------------------------------------------------
    # 公开API（对外暴露的加载方法）
    # -------------------------------------------------------------------------
    def load_package(self, package_dir: PackageDir) -> Optional[PackageName]:
        """
        加载单个包（核心流程）
        :param package_dir: 包目录绝对路径
        :return: 成功返回包名，失败返回None
        """
        logger.info(f"[Package Load Start] 包目录：{package_dir}")

        # 1. 前置准备：路径标准化 + 包合法性校验
        normalized_dir = self._normalize_path(package_dir)
        if not self._validate_package_dir(normalized_dir):
            logger.error(f"[Package Load Failed] 包目录：{normalized_dir} | 原因：包合法性校验失败")
            return None

        # 2. 解析包基础信息
        package_name = self._get_package_name(normalized_dir)
        tool_type = self._get_tool_type_by_package_dir(normalized_dir)
        func_configs = self._load_func_configs(normalized_dir)
        if not func_configs:
            logger.error(f"[Package Load Failed] 包名：{package_name} | 原因：无有效函数配置")
            return None

        # 3. 环境准备：选择全局/独立环境
        env_result = self._prepare_package_env(package_name, normalized_dir)
        if not env_result:
            logger.error(f"[Package Load Failed] 包名：{package_name} | 原因：环境准备失败")
            return None
        venv_path, venv_type = env_result

        # 4. 依赖安装：安装包所需系统/Python依赖
        if not package_name in self._tool_repo.list_packages():

            if not self._install_package_deps(package_name, normalized_dir, venv_path):
                logger.error(f"[Package Load Failed] 包名：{package_name} | 原因：依赖安装失败")
                return None

        # 5. 模块导入：加载tool.py模块（注入环境依赖）
        tool_module = self._load_tool_module(package_name, normalized_dir, venv_path)
        if not tool_module:
            logger.error(f"[Package Load Failed] 包名：{package_name} | 原因：模块导入失败")
            return None

        # 6. 函数校验：校验函数可调用性，组装函数详情
        valid_funcs = self._validate_and_assemble_funcs(package_name, tool_module, func_configs)
        if not valid_funcs:
            logger.error(f"[Package Load Failed] 包名：{package_name} | 原因：无有效可调用函数")
            return None

        # 7. 数据存储：调用仓库保存包+函数信息
        if self._tool_repo.add_package(
                package_name=package_name,
                tool_type=tool_type,
                package_dir=normalized_dir,
                venv_path=venv_path,
                venv_type=venv_type,
                funcs=valid_funcs
        ):
            logger.info(f"[Package Load Success] 包名：{package_name} | 分类：{tool_type} | 有效函数数：{len(valid_funcs)}")
            return package_name
        else:
            logger.error(f"[Package Load Failed] 包名：{package_name} | 原因：仓库存储失败")
            return None

    def load_tool_type(self, tool_type: ToolType) -> Dict[str, Any]:
        """
        加载指定分类下所有包（批量加载）
        :param tool_type: 分类名（支持字符串/Enum）
        :return: 加载结果统计
        """
        # 标准化分类名（支持Enum类型）
        tool_type_str = self._normalize_tool_type(tool_type)
        result = self._init_load_result(tool_type_str)

        # 获取分类目录
        type_dir = self._get_tool_type_dir(tool_type_str)
        if not os.path.isdir(type_dir):
            result["fail_reason"] = f"分类目录不存在：{type_dir}"
            logger.error(f"[ToolType Load Failed] 分类：{tool_type_str} | 原因：{result['fail_reason']}")
            return self._log_and_return_result(result)

        # 遍历分类下所有包目录
        for item in os.listdir(type_dir):
            item_path = os.path.join(type_dir, item)
            if not os.path.isdir(item_path):
                logger.debug(f"[ToolType Load Skip] 分类：{tool_type_str} | 原因：非目录 - {item_path}")
                continue

            result["total_package"] += 1
            package_name = self.load_package(item_path)

            if package_name:
                result["success_package"] += 1
                result["success_func"] += len(self._tool_repo.list_funcs(package_name))
            else:
                result["fail_package"].append(item)

        return self._log_and_return_result(result)

    # -------------------------------------------------------------------------
    # 内部辅助方法（私有，单一职责）
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_path(path: str) -> PackageDir:
        """标准化路径（绝对路径+去除冗余）"""
        return os.path.abspath(os.path.normpath(path))

    @staticmethod
    def _normalize_tool_type(tool_type: ToolType) -> str:
        """标准化分类名（支持Enum类型）"""
        return tool_type.value if hasattr(tool_type, "value") else str(tool_type)

    @staticmethod
    def _get_package_name(package_dir: PackageDir) -> PackageName:
        """从包目录获取包名（目录名）"""
        return os.path.basename(package_dir)

    @staticmethod
    def _get_tool_type_by_package_dir(package_dir: PackageDir) -> ToolType:
        """从包目录获取所属分类（父目录名）"""
        return os.path.basename(os.path.dirname(package_dir))

    def _get_tool_type_dir(self, tool_type: str) -> PackageDir:
        """获取分类目录路径"""
        root_dir = get_project_root()
        if not root_dir:
            logger.error("[ToolType Dir Get Failed] 原因：tool_package根目录未配置")
            return ""
        return os.path.join(self._normalize_path(root_dir), "mcp_tools", tool_type)

    def _validate_package_dir(self, package_dir: PackageDir) -> bool:
        """校验包目录合法性（存在tool.py + 通过基础校验）"""
        if not tool_package_file_check(package_dir):
            logger.error(f"[Package Validate Failed] 包目录：{package_dir} | 原因：包文件校验失败")
            return False
        return True

    def _load_func_configs(self, package_dir: PackageDir) -> Dict[FuncName, str]:
        """从config.json加载函数配置（函数名→描述）"""
        config_path = os.path.join(package_dir, "config.json")
        package_name = self._get_package_name(package_dir)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            # 提取tools节点下的函数配置（key=函数名，value=描述）
            func_configs = config_data.get("tools", {})
            if not isinstance(func_configs, dict) or len(func_configs) == 0:
                logger.warning(f"[Func Config Load Empty] 包名：{package_name} | 原因：config.json中tools节点为空")
                return {}
            logger.debug(f"[Func Config Load Success] 包名：{package_name} | 加载函数配置数：{len(func_configs)}")
            return func_configs
        except FileNotFoundError:
            logger.error(f"[Func Config Load Failed] 包名：{package_name} | 原因：config.json不存在 - {config_path}")
            return {}
        except json.JSONDecodeError:
            logger.error(f"[Func Config Load Failed] 包名：{package_name} | 原因：config.json格式错误")
            return {}
        except Exception as e:
            logger.error(f"[Func Config Load Failed] 包名：{package_name} | 原因：{str(e)}", exc_info=True)
            return {}

    def _prepare_package_env(self, package_name: PackageName, package_dir: PackageDir) -> Optional[tuple[str, str]]:
        """为包准备环境（选择全局/独立环境）"""
        try:
            deps_path = os.path.join(package_dir, "deps.toml")
            deps_exists = os.path.exists(deps_path)

            # 调用环境管理器选择环境（包名为环境标识）
            venv_path = self._dep_manager.select_venv_for_tool(
                tool_id=package_name,
                deps_script_path=deps_path if deps_exists else None
            )
            venv_type = "global" if venv_path == self._dep_manager.global_venv_path else "isolated"
            logger.debug(f"[Package Env Prepared] 包名：{package_name} | 环境路径：{venv_path} | 环境类型：{venv_type}")
            return venv_path, venv_type
        except Exception as e:
            logger.error(f"[Package Env Prepare Failed] 包名：{package_name} | 原因：{str(e)}", exc_info=True)
            return None

    def _install_package_deps(self, package_name: PackageName, package_dir: PackageDir, venv_path: str) -> bool:
        """安装包的依赖（系统依赖+Python依赖）"""
        deps_path = os.path.join(package_dir, "deps.toml")
        if not os.path.exists(deps_path):
            logger.debug(f"[Package Deps Skip] 包名：{package_name} | 原因：无deps.toml依赖配置")
            return True

        try:
            # 调用环境管理器执行依赖安装
            logger.info("-------------正在安装相关依赖---------------")
            install_result = self._dep_manager.execute_deps_script(
                deps_script_path=deps_path,
                venv_path=venv_path
            )
            # 收集失败的依赖（仅报警，不中断流程）
            failed_deps = install_result["system"]["failed"] + install_result["pip"]["failed"]
            if failed_deps:
                logger.warning(f"[Package Deps Partial Failed] 包名：{package_name} | 失败依赖：{failed_deps}")
            logger.debug(f"[Package Deps Installed] 包名：{package_name} | 依赖安装完成")
            return True
        except Exception as e:
            logger.error(f"[Package Deps Install Failed] 包名：{package_name} | 原因：{str(e)}", exc_info=True)
            return False

    def _load_tool_module(self, package_name: PackageName, package_dir: PackageDir, venv_path: str) -> Optional[Any]:
        """加载tool.py模块（注入环境的site-packages路径）"""
        tool_py_path = os.path.join(package_dir, "tool.py")
        module_name = f"package_{package_name}_module"  # 唯一模块名，避免冲突

        # 注入环境的site-packages路径（确保依赖可导入）
        site_packages = self._dep_manager._get_venv_site_packages(venv_path)
        sys.path.insert(0, site_packages)

        try:
            # 清理旧模块缓存（避免重复加载导致的问题）
            if module_name in sys.modules:
                del sys.modules[module_name]

            # 动态导入模块
            spec = spec_from_file_location(module_name, tool_py_path)
            if not spec or not spec.loader:
                raise ValueError("模块规范无效，无法加载")

            module = module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            logger.debug(f"[Tool Module Loaded] 包名：{package_name} | 模块名：{module_name}")
            return module
        except Exception as e:
            logger.error(f"[Tool Module Load Failed] 包名：{package_name} | 原因：{str(e)}", exc_info=True)
            return None
        finally:
            # 清理临时路径，避免污染全局sys.path
            if site_packages in sys.path:
                sys.path.remove(site_packages)

    def _validate_and_assemble_funcs(self,
                                     package_name: PackageName,
                                     tool_module: Any,
                                     func_configs: Dict[FuncName, str]) -> Dict[FuncName, FuncDetail]:
        """校验函数可调用性，组装函数详情字典"""
        valid_funcs = {}
        for func_name, description in func_configs.items():
            # 校验函数是否存在且可调用
            if not hasattr(tool_module, func_name):
                logger.warning(f"[Func Validate Skipped] 包名：{package_name} | 函数名：{func_name} | 原因：模块中不存在该函数")
                continue
            func_obj = getattr(tool_module, func_name)
            if not callable(func_obj):
                logger.warning(f"[Func Validate Skipped] 包名：{package_name} | 函数名：{func_name} | 原因：非可调用对象")
                continue

            # 组装函数详情（深拷贝避免外部修改）
            valid_funcs[func_name] = {
                "func": func_obj,
                "description": description
            }

        logger.debug(f"[Func Validate Completed] 包名：{package_name} | 有效函数数：{len(valid_funcs)} | 总配置数：{len(func_configs)}")
        return valid_funcs

    @staticmethod
    def _init_load_result(tool_type: str) -> Dict[str, Any]:
        """初始化分类加载结果统计字典"""
        return {
            "tool_type": tool_type,
            "total_package": 0,
            "success_package": 0,
            "fail_package": [],
            "success_func": 0,
            "fail_reason": ""
        }

    @staticmethod
    def _log_and_return_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """日志输出加载结果并返回"""
        logger.info(
            f"[ToolType Load Completed] 分类：{result['tool_type']} | "
            f"总包数：{result['total_package']} | "
            f"成功包数：{result['success_package']} | "
            f"失败包数：{len(result['fail_package'])} | "
            f"成功函数数：{result['success_func']} | "
            f"失败原因：{result['fail_reason']}"
        )
        return result


# 单例实例（默认使用全局依赖和仓库）
package_loader = PackageLoader()