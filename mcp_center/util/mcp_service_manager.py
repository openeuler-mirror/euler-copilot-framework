import os
import subprocess
import logging
from typing import Dict, List, Tuple, Optional

# 基础日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("McpServiceManager")
SERVICE_DIR="/usr/lib/sysagent/mcp_center/service"
class McpServiceManager:
    """
    超轻量MCP服务管理器（核心：仅执行系统命令，无解析、无冗余）
    所有操作等价于直接在终端执行对应的systemctl/journalctl命令
    """
    def __init__(self, service_dir: str = SERVICE_DIR):
        self.service_dir = os.path.abspath(service_dir)
        self.service_files: Dict[str, str] = {}  # 仅存储：文件名→路径（校验存在性）
        self.systemctl = "systemctl"
        self.journalctl = "journalctl"
        self._scan_services()
    # ===================== 核心操作：启动/停止/重启 =====================
    def start(self, service_filename: str) -> Tuple[bool, str]:
        """启动服务 → 等价于：systemctl start xxx.service"""

        cmd = [self.systemctl, "start", service_filename]
        return self._exec_cmd(cmd)

    def stop(self, service_filename: str) -> Tuple[bool, str]:
        """停止服务 → 等价于：systemctl stop xxx.service"""

        cmd = [self.systemctl, "stop", service_filename]
        return self._exec_cmd(cmd)

    def restart(self, service_filename: str) -> Tuple[bool, str]:
        """重启服务 → 等价于：systemctl restart xxx.service"""

        cmd = [self.systemctl, "restart", service_filename]
        return self._exec_cmd(cmd)

    # ===================== 批量操作 =====================
    def start_all(self) -> Dict[str, Tuple[bool, str]]:
        """批量启动所有服务"""
        if not self.service_files:
            self._scan_services()
        result = {}
        for filename in self.service_files.keys():
            result[filename] = self.start(filename)
        print(f"批量启动完成 → 总计：{len(result)} 个服务")
        return result

    def stop_all(self) -> Dict[str, Tuple[bool, str]]:
        """批量停止所有服务"""
        if not self.service_files:
            self._scan_services()
        result = {}
        for filename in self.service_files.keys():
            result[filename] = self.stop(filename)
        print(f"批量停止完成 → 总计：{len(result)} 个服务")
        return result

    # ===================== 状态查询：仅执行，无解析 =====================
    def get_status(self, service_filename: str) -> Tuple[bool, str]:
        """查询状态 → 等价于：systemctl status xxx.service --no-pager"""
        # --no-pager 避免分页，直接返回完整输出（和终端执行效果一致）
        cmd = [self.systemctl, "status", service_filename, "--no-pager"]
        return self._exec_cmd(cmd)

    # ===================== 日志查看：仅执行，无解析 =====================
    def get_logs(self,
                 service_filename: str,
                 lines: int = 100,
                 follow: bool = False) -> Tuple[bool, str]:
        """
        查看日志 → 等价于：
        - 查看最后N行：journalctl -u xxx.service --no-pager -n N
        - 实时跟踪：journalctl -u xxx.service -f
        """
        if follow:
            # 实时跟踪日志：直接执行，不捕获输出（和终端敲命令体验一致）
            cmd = [self.journalctl, "-u", service_filename, "-f"]
            logger.info(f"实时跟踪日志 → {service_filename}（按Ctrl+C停止）")
            try:
                subprocess.run(cmd)  # 直接执行，输出到终端
                return True, "实时日志跟踪已停止"
            except KeyboardInterrupt:
                return True, "用户终止实时日志跟踪"
            except Exception as e:
                return False, f"跟踪日志异常：{str(e)}"
        else:
            # 查看指定行数日志：返回原生输出
            cmd = [self.journalctl, "-u", service_filename, "--no-pager", "-n", str(lines)]
            return self._exec_cmd(cmd)

    # ===================== 列出所有运行中的MCP服务 =====================
    def list_running_services(self) -> List[str]:
        """
        列出service_dir目录下所有正在运行（active (running)）的MCP服务
        :return: 运行中的服务名列表
        """
        # 先扫描目录下所有.service文件
        if not self.service_files:
            self._scan_services()

        running_services = []
        for service_name in self.service_files.keys():
            # 直接执行systemctl status，精准判断是否为active (running)状态
            cmd = [self.systemctl, "status", service_name, "--no-pager", "--quiet"]
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    timeout=10
                )
                # 核心判断：输出中包含"active (running)"才判定为运行中
                output = result.stdout.lower() + result.stderr.lower()
                if "active (running)" in output:
                    running_services.append(service_name)
            except Exception:
                # 忽略查询失败的服务（如已卸载、权限不足、超时等）
                continue

        return running_services
    def _scan_services(self) -> int:
        """仅扫描目录下的.service文件，记录文件名（无解析）"""
        self.service_files.clear()
        if not os.path.isdir(self.service_dir):
            logger.error(f"Service目录不存在：{self.service_dir}")
            return 0

        for filename in os.listdir(self.service_dir):
            if filename.endswith(".service") and os.path.isfile(os.path.join(self.service_dir, filename)):
                self.service_files[filename] = os.path.join(self.service_dir, filename)

        logger.info(f"扫描完成 → 目录：{self.service_dir} | 有效.service文件：{len(self.service_files)}")
        return len(self.service_files)

    def _exec_cmd(self, cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
        """
        极致简洁的命令执行封装：仅执行，无任何额外打印
        :return: (是否成功, 错误信息/空字符串)
        """
        try:
            # 直接执行命令，原生输出到终端，不捕获stdout/stderr
            result = subprocess.run(
                cmd,
                stdout=None,
                stderr=None,
                timeout=timeout
            )
            # 成功返回 (True, "")，失败返回 (False, 空字符串)
            # 因为原生输出已经打印到终端，这里只需要返回执行结果的布尔值
            return result.returncode == 0, ""
        except subprocess.TimeoutExpired:
            # 超时仅返回错误，不打印任何信息
            return False, f"命令超时：{' '.join(cmd)}"
        except Exception as e:
            # 异常仅返回错误，不打印任何信息
            return False, str(e)
# ===================== 极简使用示例 =====================
if __name__ == "__main__":
    # 1. 初始化（指定你的.service文件目录）
    manager = McpServiceManager()
