import os
import subprocess
import toml
import sys
import logging
from typing import Any, Optional, Dict
from pkg_resources import get_distribution, DistributionNotFound
from servers.oe_cli_mcp_server.util.get_project_root import get_project_root

logger = logging.getLogger(__name__)
class DepVenvManager:
    """
    依赖与虚拟环境管理类
    聚合功能：虚拟环境生命周期管理 + 系统/Python依赖安装 + 依赖冲突检测
    """
    def __init__(self):
        """初始化：绑定虚拟环境路径、初始化日志器（公共属性一次定义）"""
        
        self.logger = logger
        self.logger.setLevel(logging.INFO)
        
        # 1. 虚拟环境路径（固定规范，适配 openEuler）
        self.project_root = get_project_root()
        if not self.project_root:
            self.project_root = os.getcwd()
            self.logger.warning(f"无法获取项目根目录，使用当前工作目录：{self.project_root}")
        
        self.venv_root = os.path.join(self.project_root, "venv")
        self.global_venv_path = os.path.join(self.venv_root, "global")
        self.isolated_venv_root = os.path.join(self.venv_root, "isolated")
        self._check_venv_integrity(self.global_venv_path, is_global=True)
        # 2. 初始化目录（确保根目录存在）
        os.makedirs(self.venv_root, exist_ok=True)
        os.makedirs(self.isolated_venv_root, exist_ok=True)
    def _check_venv_integrity(self, venv_path: str, is_global: bool = False) -> bool:
        """
        检测虚拟环境是否完整（核心检测项）
        返回：True=完整，False=不完整（自动修复或报错）
        """
        self.logger.debug(f"检测虚拟环境完整性：{venv_path}")

        # 检测项1：虚拟环境目录是否存在
        if not os.path.exists(venv_path):
            self.logger.warning(f"虚拟环境目录不存在：{venv_path}")
            if is_global:
                self.logger.info("全局环境缺失，将自动创建")
            return False

        # 检测项2：pip 可执行文件是否存在
        pip_path = os.path.join(venv_path, "bin", "pip")
        if not os.path.exists(pip_path) or not os.access(pip_path, os.X_OK):
            self.logger.error(f"虚拟环境不完整：缺少可执行的 pip → {pip_path}")
            if is_global:
                self.logger.info("尝试重新创建全局虚拟环境...")
                import shutil
                shutil.rmtree(venv_path)  # 删除不完整环境
                self.create_global_venv()  # 重新创建
                return self._check_venv_integrity(venv_path, is_global)  # 重新检测
            return False

        # 检测项3：site-packages 目录是否存在（确保依赖能安装到正确位置）
        site_packages = self._get_venv_site_packages(venv_path)
        if not os.path.exists(site_packages):
            self.logger.error(f"虚拟环境不完整：缺少 site-packages 目录 → {site_packages}")
            return False

        # 所有检测项通过
        self.logger.debug(f"虚拟环境完整：{venv_path}")
        return True

    def _get_installed_packages(self, venv_path: str) -> Dict[str, str]:
        """辅助方法：获取指定虚拟环境中已安装的Python包（包名→版本号）"""
        pip_path = self.get_venv_pip(venv_path)
        try:
            # 用 pip list --format=json 获取结构化输出，解析效率高
            result = subprocess.run(
                [pip_path, "list", "--format=json"],
                capture_output=True, text=True, check=True
            )
            packages = json.loads(result.stdout)
            # 转为字典：{包名: 版本号}（忽略大小写，比如 requests → Requests）
            return {pkg["name"].lower(): pkg["version"] for pkg in packages}
        except Exception as e:
            self.logger.error(f"获取已安装包失败：{str(e)}")
            return {}  # 异常时返回空字典，降级为全量安装（避免卡住）


    def _get_venv_site_packages(self, venv_path: str) -> str:
        """私有辅助方法：获取虚拟环境 site-packages 路径"""
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        return os.path.join(venv_path, "lib", python_version, "site-packages")

    # -------------------------- 1. 虚拟环境管理方法 --------------------------
    def create_global_venv(self) -> str:
        """创建全局共用虚拟环境"""
        if os.path.exists(self.global_venv_path):
            return self.global_venv_path
        
        self.logger.info(f"创建全局虚拟环境：{self.global_venv_path}")
        subprocess.run(
            [sys.executable, "-m", "venv", self.global_venv_path],
            check=True, capture_output=True, text=True
        )
        self.logger.info("全局虚拟环境创建完成")
        return self.global_venv_path

    def create_isolated_venv(self, tool_id: str) -> str:
        """创建独立虚拟环境（用于依赖冲突的 tool）"""
        venv_path = os.path.join(self.isolated_venv_root, tool_id)
        if os.path.exists(venv_path):
            return venv_path
        
        self.logger.warning(f"依赖冲突，创建独立虚拟环境：{venv_path}")
        subprocess.run(
            [sys.executable, "-m", "venv", venv_path],
            check=True, capture_output=True, text=True
        )
        self.logger.info("独立虚拟环境创建完成")
        return venv_path

    def delete_isolated_venv(self, tool_id: str) -> bool:
        """删除指定 tool 的独立虚拟环境（保护全局环境）"""
        venv_path = os.path.join(self.isolated_venv_root, tool_id)
        if not os.path.exists(venv_path):
            self.logger.debug(f"独立虚拟环境不存在：{venv_path}")
            return True
        
        try:
            import shutil
            shutil.rmtree(venv_path)
            self.logger.info(f"删除独立虚拟环境：{venv_path}")
            return True
        except Exception as e:
            self.logger.error(f"删除独立虚拟环境失败：{str(e)}")
            return False

    def get_venv_pip(self, venv_path: Optional[str] = None) -> str:
        """获取指定虚拟环境的 pip 路径"""
        # 优先使用指定环境，否则使用当前激活环境
        target_venv = venv_path or os.getenv("VIRTUAL_ENV")
        if not target_venv:
            raise Exception("未激活虚拟环境，请先执行 source ./venv/global/bin/activate")
        return os.path.join(target_venv, "bin", "pip")

    # -------------------------- 2. 依赖冲突检测方法 --------------------------
    def check_pip_compatibility(self, pip_deps: Dict[str, str], venv_path: str) -> bool:
        """检测 Python 依赖与目标环境的兼容性 """
        site_packages = self._get_venv_site_packages(venv_path)
        sys.path.insert(0, site_packages)
        
        try:
            for dep_name, ver_constraint in pip_deps.items():
                if not ver_constraint.strip():
                    continue  
                
                # 检查依赖是否已安装
                try:
                    installed_ver = get_distribution(dep_name).version
                except DistributionNotFound:
                    continue  # 未安装，无冲突
                
                # 版本约束校验（==/>=/<=）
                if ver_constraint.startswith("==") and installed_ver != ver_constraint[2:].strip():
                    self.logger.debug(f"版本不兼容：{dep_name}（需{ver_constraint}，当前{installed_ver}）")
                    return False
                if ver_constraint.startswith(">=") and installed_ver < ver_constraint[2:].strip():
                    self.logger.debug(f"版本过低：{dep_name}（需{ver_constraint}，当前{installed_ver}）")
                    return False
                if ver_constraint.startswith("<=") and installed_ver > ver_constraint[2:].strip():
                    self.logger.debug(f"版本过高：{dep_name}（需{ver_constraint}，当前{installed_ver}）")
                    return False
            return True
        finally:
            sys.path.remove(site_packages)

    # -------------------------- 3. 依赖安装方法 --------------------------
    def install_system_deps(self, system_deps: Dict[str, str]) -> Any:
        """安装系统依赖"""
        result = {"success": [], "failed": []}
        if not system_deps:
            return result
        
        self.logger.info("=== 开始安装系统依赖（yum）===")
        for dep_name, yum_cmd in system_deps.items():
            # 检查是否已安装
            verify_cmd = f"{dep_name} --version" if dep_name != "docker" else "docker --version"
            if subprocess.run(verify_cmd, shell=True, capture_output=True).returncode == 0:
                self.logger.debug(f"系统依赖[{dep_name}]已安装，跳过")
                result["success"].append(dep_name)
                continue
            
            # 执行 yum 安装
            try:
                self.logger.info(f"安装：{dep_name} → 命令：{yum_cmd}")
                subprocess.run(yum_cmd, shell=True, check=True, text=True)
                result["success"].append(dep_name)
            except subprocess.CalledProcessError as e:
                err_msg = f"返回码{e.returncode}：{e.stderr.strip()}"
                self.logger.error(f"系统依赖[{dep_name}]安装失败：{err_msg}")
                result["failed"].append(f"{dep_name}（{err_msg}）")
        return result

    def install_pip_deps(self, pip_deps: Dict[str, str], venv_path: str, pip_index_url: Optional[str] = None) -> Any:
        """安装Python依赖（新增：先检查已安装包，仅安装缺失的）"""
        self.logger.info(f"开始处理依赖 | 环境：{os.path.basename(venv_path)} | 需检查依赖：{list(pip_deps.keys())}")
        result = {"success": [], "failed": [], "skipped": []}  # 新增 skipped 记录跳过的依赖
        if not pip_deps:
            self.logger.warning("无需要安装的Python依赖")
            return result

        pip_path = self.get_venv_pip(venv_path)
        # 关键步骤1：获取当前环境已安装的包（格式：{包名: 版本号}）
        installed_pkgs = self._get_installed_packages(venv_path)

        # 关键步骤2：筛选出「未安装」或「版本不匹配」的依赖
        need_install = {}
        for dep_name, ver_constraint in pip_deps.items():
            # 处理版本约束（比如 ver_constraint 是 "==3.4.0"，提取版本号 "3.4.0"）
            ver_wanted = ver_constraint.strip().lstrip("==") if ver_constraint.strip() else None
            if dep_name not in installed_pkgs:
                need_install[dep_name] = ver_constraint  # 未安装，需要安装
                self.logger.info(f"包 {dep_name} 未安装，需安装版本：{ver_constraint}")
            else:
                ver_installed = installed_pkgs[dep_name]
                if ver_wanted and ver_installed != ver_wanted:
                    need_install[dep_name] = ver_constraint  # 版本不匹配，需要更新
                    self.logger.info(f"包 {dep_name} 已安装版本 {ver_installed}，需更新为：{ver_wanted}")
                else:
                    result["skipped"].append(f"{dep_name}=={ver_installed}")  # 已安装且版本匹配，跳过
                    self.logger.info(f"包 {dep_name}=={ver_installed} 已存在，跳过安装")

        # 无需安装新依赖，直接返回
        if not need_install:
            self.logger.info("所有依赖均已安装，无需额外操作")
            return result

        # 关键步骤3：仅安装筛选出的「需要安装/更新」的依赖
        self.logger.info(f"开始安装缺失/不匹配的依赖：{need_install}")
        for dep_name, ver_constraint in need_install.items():
            dep_spec = f"{dep_name}{ver_constraint.strip()}" if ver_constraint.strip() else dep_name
            install_cmd = [pip_path, "install", "-q", "--no-cache-dir"]
            if pip_index_url:
                trusted_host = pip_index_url.split("://")[-1].split("/")[0]
                install_cmd.extend(["--index-url", pip_index_url, "--trusted-host", trusted_host])
            install_cmd.append(dep_spec)

            try:
                subprocess.run(install_cmd, check=True, capture_output=True, text=True)
                result["success"].append(dep_spec)
                self.logger.info(f"✅ 安装成功：{dep_spec}")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.strip()
                self.logger.error(f"❌ 安装失败：{dep_spec} | 错误：{err_msg[:100]}")
                result["failed"].append(f"{dep_spec}（{err_msg}）")

        self.logger.info(f"依赖处理完成 | 成功：{len(result['success'])} 个 | 失败：{len(result['failed'])} 个 | 跳过：{len(result['skipped'])} 个")
        return result

    def execute_deps_script(self, deps_script_path: str, venv_path: str) -> Any:
        """执行完整依赖脚本（系统+Python依赖）"""
        if not os.path.exists(deps_script_path):
            raise FileNotFoundError(f"依赖脚本不存在：{deps_script_path}")
        
        # 读取依赖脚本
        with open(deps_script_path, "r", encoding="utf-8") as f:
            deps_data = toml.load(f)

        # 读取是否有配置pip源
        pip_index_url = deps_data.get("pip_config", {}).get("index_url")

        # 安装系统依赖 + Python依赖
        system_result = self.install_system_deps(deps_data.get("system", {}))
        pip_result = self.install_pip_deps(deps_data.get("pip", {}), venv_path, pip_index_url)

        # 输出结果
        total_ok = len(system_result["success"]) + len(pip_result["success"])
        total_fail = len(system_result["failed"]) + len(pip_result["failed"])
        self.logger.info(f"=== 依赖脚本执行完成 == 成功：{total_ok} 个 | 失败：{total_fail} 个 ===")
        
        return {"system": system_result, "pip": pip_result}

   # -------------------------- 4. tool的执行环境设置 --------------------------
    def select_venv_for_tool(self, tool_id: str, deps_script_path: Optional[str] = None) -> str:
        """为 tool 选择合适的虚拟环境（全局优先，冲突则用独立环境）"""
        # 无依赖 → 全局环境
        if not deps_script_path or not os.path.exists(deps_script_path):
            self.logger.debug(f"tool[{tool_id}]无依赖，使用全局环境")
            return self.create_global_venv()
        
        # 有依赖 → 先检查全局兼容性
        with open(deps_script_path, "r", encoding="utf-8") as f:
            pip_deps = toml.load(f).get("pip", {})
        
        global_venv = self.create_global_venv()
        if self.check_pip_compatibility(pip_deps, global_venv):
            self.logger.debug(f"tool[{tool_id}]依赖与全局环境兼容")
            return global_venv
        
        # 不兼容 → 独立环境
        return self.create_isolated_venv(tool_id)