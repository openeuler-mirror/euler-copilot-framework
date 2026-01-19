import os
import subprocess
import logging
from typing import Dict, Any

from oe_cli_mcp_server.common.get_abs_cmd import get_absolute_command_path

logger = logging.getLogger(__name__)

class DepUVManager:
    """
    UV 依赖管理器（极简版）
    仅做一件事：安装指定目录下 requirements.txt 中的依赖（完全跳过打包）
    """
    def __init__(self):
        self.uv_executable = self._get_uv_path()
        # 强制使用系统 Python 环境（避免虚拟环境干扰）
        self.python_executable = "/usr/bin/python3"

    def install_deps(self, tool_dir: str) -> Dict[str, Any]:
        """
        安装单个工具包的依赖
        :param tool_dir: 工具包目录（如 /xxx/mcp_tools/cmd_executor_tool）
        :return: 安装结果（success/error/conflict/installed）
        """
        # 1. 检查 requirements.txt 是否存在
        req_file = os.path.join(tool_dir, "requirements.txt")
        if not os.path.exists(req_file):
            logger.debug(f"[UV Deps] {tool_dir} 无 requirements.txt，跳过依赖安装")
            return {
                "success": True,
                "error": "",
                "conflict": False,
                "installed": []
            }

        # 2. 构建 UV 命令（完全兼容 pip，仅装依赖，无打包）
        cmd = [
            self.uv_executable, "pip", "install",
            "-r", req_file,          # 读取 requirements.txt
            "--system",              # 安装到系统环境（避免虚拟环境隔离）
            "--no-cache-dir",        # 禁用缓存，确保安装最新依赖
            "--quiet"                # 减少日志冗余
        ]

        try:
            # 执行命令（切换到工具包目录运行）
            proc = subprocess.run(
                cmd,
                cwd=tool_dir,
                capture_output=True,
                text=True,
                check=True  # 依赖安装失败直接抛出异常
            )

            # 解析安装成功的依赖（仅用于日志）
            installed_lines = [
                line.strip() for line in proc.stdout.split("\n")
                if "Successfully installed" in line and line.strip()
            ]
            installed_pkgs = [line.split("Successfully installed ")[1] for line in installed_lines] if installed_lines else []

            if installed_pkgs:
                logger.info(f"[UV Deps] {tool_dir} 依赖安装成功：{installed_pkgs}")
            else:
                logger.info(f"[UV Deps] {tool_dir} 依赖已最新，无需安装")

            return {
                "success": True,
                "error": "",
                "conflict": "version solving failed" in proc.stderr,  # 检测版本冲突
                "installed": installed_pkgs
            }

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip()
            # 区分「版本冲突」和「其他错误」（如网络/文件不存在）
            is_conflict = "version solving failed" in error_msg
            logger.error(f"[UV Deps] {tool_dir} 依赖安装失败：{'版本冲突' if is_conflict else '执行错误'} - {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "conflict": is_conflict,
                "installed": []
            }
        except Exception as e:
            logger.error(f"[UV Deps] {tool_dir} 依赖安装异常：{str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "conflict": False,
                "installed": []
            }
    def _get_uv_path(self):
        fix_which_command = get_absolute_command_path("which")
        result = subprocess.run(
            [fix_which_command, "uv"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )
        abs_path = result.stdout.strip()
        return abs_path