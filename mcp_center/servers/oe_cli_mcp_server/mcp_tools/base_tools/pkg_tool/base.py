import logging
import os
import subprocess
import re
from enum import Enum
from typing import Dict, List, Optional
from pydantic import Field
from config.public.base_config_loader import BaseConfig, LanguageEnum

# 初始化日志（保留基础配置）
logger = logging.getLogger("pkg_tool")
logger.setLevel(logging.INFO)
lang = BaseConfig().get_config().public_config.language

# ========== 枚举类定义（不变） ==========
class PkgActionEnum(str, Enum):
    LIST = "list"              # 列出已安装包
    INFO = "info"              # 查询包详情
    INSTALL = "install"        # 在线安装
    LOCAL_INSTALL = "local-install"  # 离线RPM安装
    UPDATE = "update"          # 更新包（单个/所有）
    UPDATE_SEC = "update-sec"  # 仅更新安全补丁
    REMOVE = "remove"          # 卸载包
    CLEAN = "clean"            # 清理缓存

class PkgCacheTypeEnum(str, Enum):
    ALL = "all"                # 清理所有缓存
    PACKAGES = "packages"      # 清理包缓存
    METADATA = "metadata"      # 清理元数据缓存

# ========== 通用工具函数（精简） ==========
def get_language() -> bool:
    """获取语言配置：True=中文，False=英文"""
    return BaseConfig().get_config().public_config.language == LanguageEnum.ZH

def init_result_dict(
        target_host: str = "127.0.0.1",
        result_type: str = "list",
        include_pkg_name: bool = True
) -> Dict:
    """初始化返回结果字典"""
    result = {
        "success": False,
        "message": "",
        "result": [] if result_type == "list" else "",
        "target": target_host,
        "pkg_name": ""
    }
    return result

def parse_pkg_action(action_str: str) -> PkgActionEnum:
    """解析字符串为PkgActionEnum"""
    try:
        return PkgActionEnum(action_str.strip().lower())
    except ValueError:
        valid_values = [e.value for e in PkgActionEnum]
        raise ValueError(f"无效的操作类型，可选枚举值：{','.join(valid_values)}")

def parse_cache_type(cache_type_str: str) -> PkgCacheTypeEnum:
    """解析字符串为PkgCacheTypeEnum"""
    try:
        return PkgCacheTypeEnum(cache_type_str.strip().lower())
    except ValueError:
        valid_values = [e.value for e in PkgCacheTypeEnum]
        raise ValueError(f"无效的缓存类型，可选枚举值：{','.join(valid_values)}")

# ========== 核心命令工具（极简实现，解决命令不存在问题） ==========
def get_cmd_path(cmd: str) -> Optional[str]:
    """获取命令绝对路径（仅遍历OpenEuler常见路径）"""
    common_paths = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    for path in common_paths:
        cmd_path = os.path.join(path, cmd)
        if os.path.exists(cmd_path) and os.access(cmd_path, os.X_OK):
            return cmd_path
    logger.warning(f"命令不存在：{cmd}")
    return None

# ========== 包管理核心类（极简修复，易读易维护） ==========
class PackageManager:
    """OpenEuler软件包管理类（精简命令调用，解决系统调用异常）"""
    def __init__(self, lang: LanguageEnum = LanguageEnum.ZH):
        self.is_zh = lang
        # 提前获取命令绝对路径（避免重复查找）
        self.dnf_path = get_cmd_path("dnf") or get_cmd_path("yum")  # 兼容yum
        self.rpm_path = get_cmd_path("rpm")

    def _msg(self, zh: str, en: str) -> str:
        """简洁多语言提示"""
        return zh if self.is_zh else en

    def _run_cmd(self, cmd: List[str]) -> Optional[str]:
        """执行命令（确保返回字符串或None，不返回字典）"""
        if not cmd:
            logger.error(self._msg("命令不能为空", "Command cannot be empty"))
            return None

        # 替换命令为绝对路径
        cmd_name = cmd[0]
        if cmd_name == "dnf" and self.dnf_path:
            cmd[0] = self.dnf_path
        elif cmd_name == "rpm" and self.rpm_path:
            cmd[0] = self.rpm_path

        try:
            logger.info(f"执行命令：{' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=30
            )
            # 确保返回的是字符串（命令输出）
            return result.stdout.strip() or "操作执行成功"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            err_msg = e.stderr.strip() or str(e)
            logger.error(f"命令执行失败：{err_msg}")
            return f"命令执行失败：{err_msg}"
        except Exception as e:
            logger.error(f"系统调用异常：{str(e)}")
            return f"系统调用异常：{str(e)}"
    # ---------- 核心功能（仅修复命令调用，不改动原有解析逻辑） ----------
    def list(self, filter_key: Optional[str] = Field(None, description="包名过滤关键词（可选）")) -> List[Dict]:
        """列出已安装软件包"""
        if not self.rpm_path:
            return [{"error": self._msg("未找到rpm命令，无法列出包", "rpm command not found")}]

        cmd = [self.rpm_path, "-qa", "--queryformat", "%{NAME}\t%{VERSION}\t%{RELEASE}\t%{ARCH}\n"]
        output = self._run_cmd(cmd)
        if not output:
            return [{"error": self._msg("列出包失败", "Failed to list packages")}]

        pkg_list = []
        for line in output.splitlines():
            if not line.strip():
                continue
            name, version, release, arch = line.split("\t", 3)
            if filter_key and filter_key.lower() not in name.lower():
                continue
            pkg_list.append({
                "name": name,
                "version": f"{version}-{release}",
                "arch": arch,
                "full_name": f"{name}-{version}-{release}.{arch}"
            })
        return pkg_list

    def info(self, pkg_name: str = Field(..., description="包名（必填）")) -> Dict:
        """查询软件包详情"""
        if not pkg_name.strip():
            return {"error": self._msg("包名不能为空", "Package name cannot be empty")}
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法查询包详情", "dnf/yum command not found")}

        cmd = [self.dnf_path, "info", pkg_name.strip()]
        output = self._run_cmd(cmd)
        if not output:
            return {"error": self._msg(f"查询包{pkg_name}详情失败", f"Failed to get info for {pkg_name}")}

        # 原有解析逻辑不变
        info_patterns = {
            "name": r"Name\s*:\s*(.+)",
            "version": r"Version\s*:\s*(.+)",
            "release": r"Release\s*:\s*(.+)",
            "arch": r"Architecture\s*:\s*(.+)",
            "installed_size": r"Installed Size\s*:\s*(.+)",
            "repo": r"From Repository\s*:\s*(.+)",
            "summary": r"Summary\s*:\s*(.+)",
            "license": r"License\s*:\s*(.+)",
            "url": r"URL\s*:\s*(.+)"
        }
        pkg_info = {}
        for key, pattern in info_patterns.items():
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                pkg_info[key] = match.group(1).strip()

        return pkg_info if pkg_info else {"error": self._msg(f"未找到包{pkg_name}的信息", f"No info found for {pkg_name}")}

    def install(self,
                pkg_name: str = Field(..., description="包名（必填）"),
                yes: bool = Field(True, description="自动确认（默认True）")) -> Dict:
        """在线安装软件包"""
        if not pkg_name.strip():
            return {"error": self._msg("包名不能为空", "Package name cannot be empty")}
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法安装包", "dnf/yum command not found")}

        cmd = [self.dnf_path, "install", pkg_name.strip()]
        if yes:
            cmd.append("-y")
        output = self._run_cmd(cmd)
        return {"message": output} if output else {"error": self._msg(f"安装包{pkg_name}失败", f"Failed to install {pkg_name}")}

    def local_install(self,
                      rpm_path: str = Field(..., description="RPM文件路径（必填）"),
                      yes: bool = Field(True, description="自动确认（默认True）")) -> Dict:
        """离线安装RPM包"""
        if not rpm_path.strip():
            return {"error": self._msg("RPM路径不能为空", "RPM path cannot be empty")}
        if not os.path.exists(rpm_path.strip()):
            return {"error": self._msg(f"RPM文件不存在：{rpm_path}", f"RPM file not found: {rpm_path}")}
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法安装RPM", "dnf/yum command not found")}

        cmd = [self.dnf_path, "localinstall", rpm_path.strip()]
        if yes:
            cmd.append("-y")
        output = self._run_cmd(cmd)
        return {"message": output} if output else {"error": self._msg("安装RPM失败", "Failed to install RPM")}

    def update(self,
               pkg_name: Optional[str] = Field(None, description="包名（为空则更新所有）"),
               yes: bool = Field(True, description="自动确认（默认True）")) -> Dict:
        """更新软件包"""
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法更新包", "dnf/yum command not found")}

        cmd = [self.dnf_path, "update"]
        if pkg_name:
            cmd.append(pkg_name.strip())
        if yes:
            cmd.append("-y")
        output = self._run_cmd(cmd)
        return {"message": output} if output else {"error": self._msg("更新包失败", "Failed to update package")}

    def update_sec(self,
                   yes: bool = Field(True, description="自动确认（默认True）")) -> Dict:
        """仅更新安全补丁"""
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法更新安全补丁", "dnf/yum command not found")}

        cmd = [self.dnf_path, "update", "--security"]
        if yes:
            cmd.append("-y")
        output = self._run_cmd(cmd)
        return {"message": output} if output else {"error": self._msg("更新安全补丁失败", "Failed to update security patches")}

    def remove(self,
               pkg_name: str = Field(..., description="包名（必填）"),
               yes: bool = Field(True, description="自动确认（默认True）")) -> Dict:
        """卸载软件包"""
        if not pkg_name.strip():
            return {"error": self._msg("包名不能为空", "Package name cannot be empty")}
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法卸载包", "dnf/yum command not found")}

        cmd = [self.dnf_path, "remove", pkg_name.strip()]
        if yes:
            cmd.append("-y")
        output = self._run_cmd(cmd)
        return {"message": output} if output else {"error": self._msg(f"卸载包{pkg_name}失败", f"Failed to remove {pkg_name}")}

    def clean(self,
              cache_type: PkgCacheTypeEnum = Field(PkgCacheTypeEnum.ALL, description="缓存类型（默认all）")) -> Dict:
        """清理缓存（修复结果处理逻辑）"""
        if not self.dnf_path:
            return {"error": self._msg("未找到dnf/yum命令，无法清理缓存", "dnf/yum command not found")}

        cmd = [self.dnf_path, "clean", cache_type.value]
        output = self._run_cmd(cmd)  # 此时 output 是字符串或None

        # 直接返回结果，不调用 splitlines()（或只在 output 是字符串时调用）
        if output and "失败" not in output:
            return {"message": self._msg(f"缓存清理成功（类型：{cache_type.value}）", f"Cache cleaned successfully (type: {cache_type.value})")}
        else:
            return {"error": self._msg(f"缓存清理失败：{output or '未知错误'}", f"Failed to clean cache: {output or 'Unknown error'}")}