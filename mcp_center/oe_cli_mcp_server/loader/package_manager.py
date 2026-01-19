"""
包管理器（核心工具包管理）
核心职责：统一管理工具包的加载/卸载/查询/列表，统筹所有工具包生命周期
- 核心能力：加载包、卸载包、查询包/函数、列出所有包/函数
- 设计原则：单一职责、无状态、结果导向、最小冗余
- 依赖：DepUVManager（UV 依赖管理，移除 venv，适配 requirements.txt）
- 命名规范：统一用 Package（包）指代工具包，Tool/Func 指代包内的工具函数
- 存储优化：使用你定义的 Pydantic Model (Tool/Package) 保证类型安全
- 极简卸载：仅删除物理目录，内存信息靠重启清理（无 venv 环境）
"""

import os
import sys
import json
import logging
import shutil
from typing import Dict, Optional, Any, List
from importlib.util import spec_from_file_location, module_from_spec

# 内部依赖
from config.public.base_config_loader import BaseConfig, LanguageEnum
from oe_cli_mcp_server.loader.dependency import DepUVManager  # 已适配 requirements.txt 的版本
from oe_cli_mcp_server.common.get_project_root import get_project_root
from oe_cli_mcp_server.common.tool_package_file_check import tool_package_file_check
# 导入你定义的 Pydantic 模型
from oe_cli_mcp_server.schema.loader import Tool, Package

# 类型别名（精准对齐语义，适配你的 Pydantic 模型）
PackageName = str          # 工具包名称（目录名）
PackageDir = str           # 工具包目录路径
ToolFuncName = str         # 包内的工具函数名称
ToolDict = Dict[ToolFuncName, Tool]  # 函数名 → Tool对象
PackageDict = Dict[PackageName, Package]  # 包名 → Package对象

# 全局配置
logger = logging.getLogger(__name__)
DEFAULT_PACKAGE_ROOT = os.path.join(get_project_root() or "", "oe_cli_mcp_server/mcp_tools")

class PackageManager:
    """
    工具包管理器（严格适配你定义的 Tool/Package 模型，适配 UV + requirements.txt）
    核心逻辑：一个 Package 包含多个 Tool/Func，统一管理包的生命周期
    存储：使用你定义的 Pydantic 模型，仅保留核心字段，无 venv 相关逻辑
    卸载：仅删物理目录，内存信息靠重启重建
    """
    def __init__(self,
                 dep_manager: Optional[DepUVManager] = None,
                 package_root_dir: str = DEFAULT_PACKAGE_ROOT):
        """
        初始化管理器
        :param dep_manager: UV 依赖管理器（默认自动创建，适配 requirements.txt）
        :param package_root_dir: 工具包根目录
        """
        # 依赖注入：UV 管理器（适配 requirements.txt）
        self._dep_manager = dep_manager or DepUVManager()
        self._package_root = self._normalize_path(package_root_dir)

        # 内存存储（严格使用你定义的 Pydantic 模型）
        self._packages: PackageDict = {}          # 包名 → Package对象
        self._tool_funcs: ToolDict = {}           # 函数名 → Tool对象

        logger.info(f"PackageManager 初始化完成 | 工具包根目录：{self._package_root} | 依赖管理器：UV + requirements.txt（系统环境）")

    # -------------------------------------------------------------------------
    # 核心业务能力（增/删/查/列表）- 适配你的 Pydantic 模型（无改动）
    # -------------------------------------------------------------------------
    def load_package(self, package_dir: PackageDir) -> Optional[PackageName]:
        """
        加载单个工具包（核心）
        :param package_dir: 包目录绝对路径
        :return: 成功返回包名，失败返回None
        """
        if not package_dir:
            logger.error("[Package Load Failed] 原因：包目录不能为空")
            return None

        logger.info(f"[Package Load] 开始加载工具包：{package_dir}")

        # 1. 基础校验
        package_dir = self._normalize_path(package_dir)
        if not self._validate_package_dir(package_dir):
            return None

        package_name = self._get_package_name(package_dir)
        # 避免重复加载
        if package_name in self._packages:
            logger.warning(f"[Package Load] 包 {package_name} 已加载，跳过")
            return package_name

        # 2. 加载包内函数配置
        func_configs = self._load_package_func_configs(package_dir)
        if not func_configs:
            logger.error(f"[Package Load] 包 {package_name} 无有效工具函数配置")
            return None

        # 3. 安装包依赖（UV + requirements.txt）【核心修改：仅传目录，不再传 pyproject.toml】
        if not self._install_package_deps(package_name, package_dir):
            logger.error(f"[Package Load] 包 {package_name} 依赖安装失败")
            return None

        # 4. 加载包工具模块（系统环境）
        tool_module = self._load_package_tool_module(package_name, package_dir)
        if not tool_module:
            logger.error(f"[Package Load] 包 {package_name} 工具模块加载失败")
            return None

        # 5. 创建你定义的 Package 对象（严格匹配字段）
        try:
            package_obj = Package(
                name=package_name,
                package_dir=package_dir,
                funcs=[]  # 先占位，后续填充
            )
            self._packages[package_name] = package_obj
        except Exception as e:
            logger.error(f"[Package Load] 创建 Package 对象失败：{str(e)}")
            return None

        # 6. 校验并组装 Tool 对象（严格匹配你的模型）
        valid_funcs = self._validate_package_tool_funcs(package_name, tool_module, func_configs, package_obj)
        if not valid_funcs:
            logger.error(f"[Package Load] 包 {package_name} 无有效工具函数")
            del self._packages[package_name]  # 回滚
            return None

        # 7. 更新 Package 对象的 funcs 字段
        package_obj.funcs = list(valid_funcs.keys())
        self._tool_funcs.update(valid_funcs)

        logger.info(f"[Package Load] 包 {package_name} 加载成功 | 有效工具函数数：{len(valid_funcs)}")
        return package_name

    def load_all_packages(self) -> Dict[str, Any]:
        """
        加载所有工具包（批量）
        :return: 加载结果统计
        """
        result = {
            "total_package": 0,
            "success_package": 0,
            "fail_package": [],
            "success_func": 0
        }

        if not os.path.isdir(self._package_root):
            logger.error(f"[Package Load All] 工具包根目录不存在：{self._package_root}")
            result["fail_reason"] = "工具包根目录不存在"
            return result

        # 遍历所有含 tool.py 的包目录
        for root, dirs, files in os.walk(self._package_root):
            if "tool.py" not in files:
                continue

            result["total_package"] += 1
            package_name = self.load_package(root)

            if package_name:
                result["success_package"] += 1
                result["success_func"] += len(self.list_package_funcs(package_name))
            else:
                result["fail_package"].append(os.path.basename(root))

        logger.info(f"[Package Load All] 批量加载完成 | 总包数：{result['total_package']} | 成功：{result['success_package']}")
        return result

    def unload_package(self, package_name: PackageName, delete_dir: bool = True) -> bool:
        """
        卸载单个工具包（极简版）
        核心逻辑：仅删除物理目录，内存信息靠重启清理
        :param package_name: 包名
        :param delete_dir: 是否物理删除包目录（默认True）
        :return: 成功返回True，失败返回False
        """
        if not package_name:
            logger.error("[Package Unload Failed] 原因：包名不能为空")
            return False

        logger.info(f"[Package Unload] 开始卸载工具包：{package_name} | 删除目录：{delete_dir}")

        # 1. 校验包存在性
        if package_name not in self._packages:
            logger.error(f"[Package Unload] 包 {package_name} 不存在")
            return False

        package_obj = self._packages[package_name]

        # 2. 物理删除包目录（核心）
        if delete_dir:
            self._delete_package_dir(package_obj.package_dir)

        # 极简设计：不清理内存，靠重启重建
        logger.info(f"[Package Unload] 包 {package_name} 卸载成功（需重启生效）")
        return True

    def get_package_info(self, package_name: PackageName) -> Optional[Package]:
        """
        查询单个包的完整信息（返回你定义的 Package 对象）
        :param package_name: 包名
        :return: Package对象，包不存在返回None
        """
        if not package_name:
            logger.error("[Package Query Failed] 原因：包名不能为空")
            return None

        return self._packages.get(package_name)

    def get_tool_func_info(self, func_name: ToolFuncName) -> Optional[Tool]:
        """
        查询单个工具函数的详情（返回你定义的 Tool 对象）
        :param func_name: 工具函数名（全局唯一）
        :return: Tool对象，函数不存在返回None
        """
        if not func_name:
            logger.error("[Func Query Failed] 原因：工具函数名不能为空")
            return None

        return self._tool_funcs.get(func_name)

    def list_all_packages(self) -> List[PackageName]:
        """列出所有已加载的工具包名（按添加顺序）"""
        return list(self._packages.keys())

    def list_package_funcs(self, package_name: Optional[PackageName] = None) -> List[ToolFuncName]:
        """
        列出工具函数名（精准区分：包级/全局）
        :param package_name: 可选，指定包名则列出该包的函数，否则列出所有函数
        :return: 工具函数名列表
        """
        if package_name:
            if not package_name:
                logger.error("[Func List Failed] 原因：包名不能为空")
                return []
            package_obj = self._packages.get(package_name)
            if not package_obj:
                logger.warning(f"[Func List] 包 {package_name} 不存在，无工具函数")
                return []
            return package_obj.funcs
        # 列出所有函数（按名称排序）
        return sorted(self._tool_funcs.keys())

    def clear_all_packages(self, delete_dir: bool = True) -> bool:
        """
        清空所有已加载的工具包
        :param delete_dir: 是否物理删除包目录
        :return: 成功返回True
        """
        logger.info("[Package Clear] 开始清空所有工具包")
        for package_name in list(self._packages.keys()):
            self.unload_package(package_name, delete_dir)

        # 清理内存缓存（非必须，重启会重建）
        self._tool_funcs.clear()
        logger.info("[Package Clear] 所有工具包已清空（需重启生效）")
        return True

    # 兼容别名
    clear_all = clear_all_packages

    # -------------------------------------------------------------------------
    # 辅助方法（无改动）
    # -------------------------------------------------------------------------
    @staticmethod
    def _init_empty_package_result(fail_reason: str) -> Dict[str, Any]:
        """初始化空的包加载结果统计"""
        return {
            "total_package": 0,
            "success_package": 0,
            "fail_package": [],
            "success_func": 0,
            "fail_reason": fail_reason
        }

    # -------------------------------------------------------------------------
    # 核心工具方法（适配你的 Pydantic 模型，仅修改 _install_package_deps）
    # -------------------------------------------------------------------------
    @staticmethod
    def _normalize_path(path: str) -> str:
        """标准化路径（绝对路径+去除冗余）"""
        return os.path.abspath(os.path.normpath(path)) if path else ""

    @staticmethod
    def _get_package_name(package_dir: PackageDir) -> PackageName:
        """从包目录获取包名（目录名）"""
        return os.path.basename(package_dir)

    def _validate_package_dir(self, package_dir: PackageDir) -> bool:
        """校验包目录合法性（存在tool.py + 通过基础校验）"""
        if not os.path.isdir(package_dir):
            logger.error(f"[Package Validate Failed] 包目录不存在：{package_dir}")
            return False
        if not tool_package_file_check(package_dir):
            logger.error(f"[Package Validate Failed] 包文件校验失败：{package_dir}")
            return False
        return True

    def _load_package_func_configs(self, package_dir: PackageDir) -> Dict[ToolFuncName, str]:
        """加载包内的工具函数配置（config.json → tools 节点）
        返回：{函数名: 对应语言的描述字符串}
        """
        config_path = os.path.join(package_dir, "config.json")
        package_name = self._get_package_name(package_dir)

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            func_configs = config_data.get("tools", {})

            if not isinstance(func_configs, dict) or len(func_configs) == 0:
                logger.warning(f"[Package Config] 包 {package_name} 无有效工具函数配置")
                return {}

            # 读取全局语言配置
            self.language = BaseConfig().get_config().public_config.language

            # 提取对应语言的描述
            final_func_configs = {}
            for func_name, desc_dict in func_configs.items():
                if not isinstance(desc_dict, dict):
                    final_func_configs[func_name] = str(desc_dict)
                    logger.debug(f"[Package Config] 包 {package_name} 函数 {func_name} 描述非字典，直接使用：{desc_dict}")
                    continue

                # 优先取指定语言，兜底中文
                final_desc = desc_dict.get(self.language, desc_dict.get(LanguageEnum.ZH.value, ""))
                if not final_desc:
                    logger.warning(f"[Package Config] 包 {package_name} 函数 {func_name} 无有效描述")

                final_func_configs[func_name] = final_desc

            return final_func_configs
        except Exception as e:
            logger.error(f"[Package Config] 加载 {package_name} 配置失败：{str(e)}", exc_info=True)
            return {}

    def _install_package_deps(self, package_name: PackageName, package_dir: PackageDir) -> bool:
        """
        安装包的依赖（核心修改：UV + requirements.txt）
        :param package_name: 包名
        :param package_dir: 包目录（DepUVManager 会自动找该目录下的 requirements.txt）
        :return: 成功返回True，失败返回False
        """
        # 不再校验 pyproject.toml，直接调用 DepUVManager（它会自动找 requirements.txt）
        try:
            # 调用 UV 管理器安装依赖（传目录，不传文件）
            install_result = self._dep_manager.install_deps(package_dir)
            if not install_result["success"]:
                if install_result["conflict"]:
                    logger.error(f"[Package Deps] 包 {package_name} 依赖版本冲突：{install_result['error']}")
                else:
                    logger.error(f"[Package Deps] 包 {package_name} 依赖安装失败：{install_result['error']}")
                return False

            if install_result["installed"]:
                logger.info(f"[Package Deps] 包 {package_name} 依赖安装成功：{install_result['installed']}")
            else:
                logger.debug(f"[Package Deps] 包 {package_name} 无依赖或依赖已最新")
            return True
        except Exception as e:
            logger.error(f"[Package Deps] 包 {package_name} 依赖安装异常：{str(e)}", exc_info=True)
            return False

    def _load_package_tool_module(self, package_name: PackageName, package_dir: PackageDir) -> Optional[Any]:
        """加载包内的tool.py模块（系统环境，无 venv 路径注入）"""
        tool_py_path = os.path.join(package_dir, "tool.py")
        module_name = f"package_{package_name}_tool_module"

        try:
            # 清理旧模块缓存
            if module_name in sys.modules:
                del sys.modules[module_name]

            # 动态导入模块
            spec = spec_from_file_location(module_name, tool_py_path)
            if not spec or not spec.loader:
                raise ValueError("工具模块规范无效")

            module = module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            logger.error(f"[Package Module] 加载 {package_name} 工具模块失败：{str(e)}", exc_info=True)
            return None

    def _validate_package_tool_funcs(self,
                                     package_name: PackageName,
                                     tool_module: Any,
                                     func_configs: Dict[ToolFuncName, str],
                                     package_obj: Package) -> ToolDict:
        """
        校验并组装包内的工具函数（返回你定义的 Tool 对象字典）
        """
        valid_funcs = {}
        for func_name, description in func_configs.items():
            # 校验函数存在且可调用
            if not hasattr(tool_module, func_name):
                logger.warning(f"[Package Func] 包 {package_name} 缺少工具函数：{func_name}")
                continue
            func_obj = getattr(tool_module, func_name)
            if not callable(func_obj):
                logger.warning(f"[Package Func] 包 {package_name} 的 {func_name} 非可调用工具函数")
                continue

            # 创建你定义的 Tool 对象（严格匹配字段）
            tool_obj = Tool(
                name=func_name,
                func=func_obj,
                description=description,
                package=package_name,
                package_dir=package_obj.package_dir
            )
            valid_funcs[func_name] = tool_obj
        return valid_funcs

    def _delete_package_dir(self, package_dir: PackageDir) -> bool:
        """物理删除包目录"""
        try:
            if os.path.exists(package_dir):
                shutil.rmtree(package_dir)
                logger.info(f"[Package Dir] 物理删除包目录：{package_dir}")
                return True
            logger.debug(f"[Package Dir] 包目录不存在，无需删除：{package_dir}")
            return False
        except Exception as e:
            logger.error(f"[Package Dir] 删除 {package_dir} 失败：{str(e)}", exc_info=True)
            return False

# 全局单例实例
package_manager = PackageManager()