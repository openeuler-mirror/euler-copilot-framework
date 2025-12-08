import logging
import os
import platform
import subprocess
import re
from enum import Enum
from typing import Dict, List, Optional

from config.public.base_config_loader import LanguageEnum, BaseConfig

# 初始化日志
logger = logging.getLogger("sys_info_tool")
logger.setLevel(logging.INFO)

# ========== 枚举类定义（不变） ==========
class InfoTypeEnum(str, Enum):
    """信息类型枚举（对应需求的3大类）"""
    # 系统类
    OS = "os"          # 版本/内核
    LOAD = "load"      # 系统负载
    UPTIME = "uptime"  # 运行时间
    # 硬件类
    CPU = "cpu"        # CPU信息
    MEM = "mem"        # 内存占用
    DISK = "disk"      # 磁盘分区/使用率
    GPU = "gpu"        # 显卡状态
    NET = "net"        # 网卡/IP
    # 安全类
    SELINUX = "selinux"# SELinux状态
    FIREWALL = "firewall"  # 防火墙规则

# ========== 通用工具函数（不变） ==========
def get_language() -> LanguageEnum:
    """获取全局语言配置"""
    return BaseConfig().get_config().public_config.language

def is_zh() -> bool:
    """判断是否为中文环境"""
    return get_language() == LanguageEnum.ZH

def init_result_dict(
        target_host: str = "127.0.0.1",
        result_type: str = "dict"
) -> Dict:
    """初始化返回结果字典（result为嵌套字典，key为信息类型）"""
    return {
        "success": False,
        "message": "",
        "result": {},  # 格式：{"cpu": {...}, "mem": {...}, ...}
        "target": target_host,
        "info_types": []  # 记录已采集的信息类型列表
    }

def parse_info_types(info_type_list: List[str]) -> List[InfoTypeEnum]:
    """解析字符串列表为InfoTypeEnum列表（适配大模型输入）"""
    if not info_type_list:
        valid_values = [e.value for e in InfoTypeEnum]
        zh_msg = f"信息类型列表不能为空，可选枚举值：{','.join(valid_values)}"
        en_msg = f"Info type list cannot be empty, optional enum values: {','.join(valid_values)}"
        raise ValueError(zh_msg if is_zh() else en_msg)

    parsed_enums = []
    valid_values = [e.value for e in InfoTypeEnum]
    for info_type_str in info_type_list:
        try:
            parsed_enums.append(InfoTypeEnum(info_type_str.strip().lower()))
        except ValueError:
            zh_msg = f"无效的信息类型：{info_type_str}，可选枚举值：{','.join(valid_values)}"
            en_msg = f"Invalid info type: {info_type_str}, optional enum values: {','.join(valid_values)}"
            raise ValueError(zh_msg if is_zh() else en_msg)
    return parsed_enums

# ========== 系统信息采集核心类（修复命令不存在问题） ==========
class SystemInfoCollector:
    """系统/硬件/安全信息采集类（优先Python原生，必要时调用系统命令）"""
    def __init__(self):
        self.lang = get_language()

    def _get_msg(self, zh_msg: str, en_msg: str) -> str:
        """多语言提示"""
        return zh_msg if self.lang == LanguageEnum.ZH else en_msg

    def _run_cmd_safe(self, cmd: List[str]) -> Optional[str]:
        """安全执行系统命令（命令不存在/执行失败返回None，不抛出异常）"""
        # 检查命令是否存在（获取绝对路径）
        cmd_name = cmd[0]
        cmd_path = self._find_cmd_absolute_path(cmd_name)
        if not cmd_path:
            logger.warning(self._get_msg(f"命令不存在：{cmd_name}", f"Command not found: {cmd_name}"))
            return None

        # 替换为绝对路径执行
        cmd[0] = cmd_path
        try:
            logger.info(f"执行系统命令：{' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=10  # 超时保护：10秒
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or e.stdout.strip()
            logger.error(self._get_msg(f"命令执行失败：{cmd_name}，错误：{error_msg}", f"Command failed: {cmd_name}, error: {error_msg}"))
            return None
        except subprocess.TimeoutExpired:
            logger.error(self._get_msg(f"命令执行超时：{cmd_name}", f"Command timeout: {cmd_name}"))
            return None
        except Exception as e:
            logger.error(self._get_msg(f"系统调用异常：{cmd_name}，错误：{str(e)}", f"System call exception: {cmd_name}, error: {str(e)}"))
            return None

    def _find_cmd_absolute_path(self, cmd: str) -> Optional[str]:
        """辅助函数：查找命令的绝对路径（兼容特殊情况）"""
        try:
            # 用 which 命令查找（若 which 存在）
            which_result = self._run_cmd_safe(["which", cmd])
            if which_result:
                return which_result.strip()
        except Exception:
            pass

        # which 不存在时，遍历常见路径
        common_paths = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin"]
        for path in common_paths:
            cmd_path = os.path.join(path, cmd)
            if os.path.exists(cmd_path) and os.access(cmd_path, os.X_OK):
                return cmd_path
        return None

    # ---------- 系统类信息 ----------
    def get_os_info(self) -> Dict:
        """获取系统版本/内核信息（无命令依赖，不变）"""
        os_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "kernel": platform.uname().release,
            "architecture": platform.machine()
        }
        # 补充OpenEuler版本（通过/etc/os-release）
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            os_info["pretty_name"] = line.strip().split("=")[1].strip('"')
                        elif line.startswith("VERSION_ID="):
                            os_info["version_id"] = line.strip().split("=")[1].strip('"')
            except Exception as e:
                logger.error(self._get_msg(f"读取os-release失败：{str(e)}", f"Failed to read os-release: {str(e)}"))
        return os_info

    def get_load_info(self) -> Dict:
        """获取系统负载（无命令依赖，不变）"""
        try:
            load_avg = os.getloadavg()
            return {
                "1min": load_avg[0],
                "5min": load_avg[1],
                "15min": load_avg[2],
                "cpu_count": os.cpu_count() or 0
            }
        except Exception as e:
            logger.error(self._get_msg(f"获取系统负载失败：{str(e)}", f"Failed to get load avg: {str(e)}"))
            return {"error": self._get_msg("获取系统负载失败", "Failed to get load average")}

    def get_uptime_info(self) -> Dict:
        """获取系统运行时间（修复uptime命令不存在问题）"""
        uptime_output = self._run_cmd_safe(["uptime", "-p"])
        if uptime_output:
            return {"uptime": uptime_output}
        else:
            # 命令不存在时，通过/proc/uptime计算（Python原生方式）
            try:
                with open("/proc/uptime", "r", encoding="utf-8") as f:
                    total_seconds = float(f.readline().split()[0])
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    uptime_str = self._get_msg(f"运行 {hours} 小时 {minutes} 分钟", f"up {hours} hours, {minutes} minutes")
                    return {"uptime": uptime_str, "note": self._get_msg("基于/proc/uptime计算", "Calculated from /proc/uptime")}
            except Exception as e:
                logger.error(self._get_msg(f"获取运行时间失败：{str(e)}", f"Failed to get uptime: {str(e)}"))
                return {"error": self._get_msg("获取运行时间失败", "Failed to get uptime")}

    # ---------- 硬件类信息 ----------
    def get_cpu_info(self) -> Dict:
        """获取CPU型号/核心信息（无命令依赖，不变）"""
        cpu_info = {}
        try:
            # 通过/proc/cpuinfo获取
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_info["model"] = line.strip().split(":")[1].strip()
                            break
                    # 获取CPU核心数
                    cpu_info["physical_cores"] = os.cpu_count() or 0
            return cpu_info
        except Exception as e:
            logger.error(self._get_msg(f"获取CPU信息失败：{str(e)}", f"Failed to get CPU info: {str(e)}"))
            return {"error": self._get_msg("获取CPU信息失败", "Failed to get CPU information")}

    def get_mem_info(self) -> Dict:
        """获取内存占用信息（无命令依赖，不变）"""
        mem_info = {}
        try:
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_info["total_mb"] = int(line.strip().split()[1]) // 1024
                        elif line.startswith("MemFree:"):
                            mem_info["free_mb"] = int(line.strip().split()[1]) // 1024
                        elif line.startswith("MemAvailable:"):
                            mem_info["available_mb"] = int(line.strip().split()[1]) // 1024
                if "total_mb" in mem_info and "free_mb" in mem_info:
                    mem_info["used_mb"] = mem_info["total_mb"] - mem_info["free_mb"]
                    mem_info["used_percent"] = round(mem_info["used_mb"] / mem_info["total_mb"] * 100, 2)
            return mem_info
        except Exception as e:
            logger.error(self._get_msg(f"获取内存信息失败：{str(e)}", f"Failed to get memory info: {str(e)}"))
            return {"error": self._get_msg("获取内存信息失败", "Failed to get memory information")}

    def get_disk_info(self) -> List[Dict]:
        """获取磁盘分区/使用率信息（优化命令检查）"""
        disk_list = []
        # 直接指定 df 绝对路径（OpenEuler 99% 情况下的路径）
        df_cmd = self._find_cmd_absolute_path("df")
        if not df_cmd:
            logger.error(self._get_msg("未找到df命令，无法获取磁盘信息", "df command not found, cannot get disk info"))
            return [{"error": self._get_msg("未找到df命令，请安装coreutils包", "df command not found, please install coreutils")}]

        try:
            # 用绝对路径执行 df 命令（避免 PATH 问题）
            disk_output = self._run_cmd_safe([
                df_cmd, "-h", "-T",
                "--output=source,fstype,size,used,avail,pcent,mountpoint"
            ])
            if not disk_output:
                return [{"error": self._get_msg("df命令执行失败，无法获取磁盘信息", "df command execution failed")}]

            # 解析输出
            lines = [line.strip() for line in disk_output.splitlines() if line.strip()]
            if len(lines) < 2:
                logger.warning(self._get_msg("df未返回有效磁盘信息", "df returned no valid disk info"))
                return [{"error": self._get_msg("df未返回有效磁盘信息", "df returned no valid disk information")}]

            for line in lines[1:]:
                parts = re.split(r"\s+", line, maxsplit=6)
                if len(parts) != 7:
                    logger.debug(f"跳过无效行：{line}")
                    continue
                used_percent = parts[5].strip("%") if "%" in parts[5] else parts[5]
                disk_list.append({
                    "device": parts[0],
                    "fstype": parts[1],
                    "size": parts[2],
                    "used": parts[3],
                    "avail": parts[4],
                    "used_percent": used_percent,
                    "mountpoint": parts[6]
                })
            return disk_list if disk_list else [{"error": self._get_msg("未检测到有效磁盘分区", "No valid disk partitions detected")}]
        except Exception as e:
            logger.error(self._get_msg(f"获取磁盘信息失败：{str(e)}", f"Failed to get disk info: {str(e)}"))
            return [{"error": self._get_msg("获取磁盘信息失败", "Failed to get disk information")}]

    def get_gpu_info(self) -> List[Dict]:
        """获取显卡状态（修复nvidia-smi命令不存在问题）"""
        gpu_list = []
        # 检查nvidia-smi是否存在
        nvidia_smi_path = self._find_cmd_absolute_path("nvidia-smi")
        if not nvidia_smi_path:
            logger.warning(self._get_msg("未检测到nvidia-smi命令，跳过GPU信息采集", "nvidia-smi not found, skip GPU info collection"))
            return [{"note": self._get_msg("未检测到nvidia-smi命令（无NVIDIA显卡或未安装驱动）", "nvidia-smi not found (no NVIDIA GPU or driver)")}]

        # 执行命令
        gpu_output = self._run_cmd_safe([
            nvidia_smi_path,
            "--query-gpu=name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits"
        ])
        if gpu_output:
            for line in gpu_output.splitlines():
                if not line.strip():
                    continue
                parts = line.strip().split(", ")
                if len(parts) != 4:
                    logger.debug(f"跳过无效GPU行：{line}")
                    continue
                name, mem_total, mem_used, util = parts
                gpu_list.append({
                    "name": name.strip(),
                    "memory_total_mb": int(mem_total) if mem_total.isdigit() else 0,
                    "memory_used_mb": int(mem_used) if mem_used.isdigit() else 0,
                    "utilization_percent": int(util) if util.isdigit() else 0
                })
            return gpu_list if gpu_list else [{"note": self._get_msg("未检测到可用GPU", "No available GPU detected")}]
        else:
            return [{"error": self._get_msg("GPU信息采集失败", "Failed to collect GPU information")}]

    def get_net_info(self) -> List[Dict]:
        """获取网卡/IP信息（修复ip命令不存在问题）"""
        # 检查ip命令是否存在
        ip_cmd_path = self._find_cmd_absolute_path("ip")
        if not ip_cmd_path:
            logger.warning(self._get_msg("未找到ip命令，尝试通过/proc/net/dev获取网卡信息", "ip command not found, try to get net info from /proc/net/dev"))
            # 降级方案：通过/proc/net/dev获取网卡名称（无IP信息）
            net_list = []
            try:
                with open("/proc/net/dev", "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("Inter-|") and not line.startswith(" face |")]
                    for line in lines:
                        if ":" in line:
                            iface = line.split(":")[0].strip()
                            net_list.append({
                                "interface": iface,
                                "ips": [{"note": self._get_msg("ip命令不存在，无法获取IP信息", "ip command not found, cannot get IP info")}]
                            })
                return net_list
            except Exception as e:
                logger.error(self._get_msg(f"获取网络信息失败：{str(e)}", f"Failed to get net info: {str(e)}"))
                return [{"error": self._get_msg("获取网络信息失败（ip命令不存在）", "Failed to get network information (ip command not found)")}]

        # ip命令存在，正常采集
        net_output = self._run_cmd_safe([ip_cmd_path, "addr", "show"])
        if not net_output:
            return [{"error": self._get_msg("ip命令执行失败，无法获取网络信息", "ip command execution failed")}]

        net_list = []
        current_iface = None
        for line in net_output.splitlines():
            line = line.strip()
            if line.startswith(("1:", "2:", "3:", "4:", "5:")):  # 网卡名称行
                current_iface = line.split(":")[1].strip()
                net_list.append({"interface": current_iface, "ips": []})
            elif current_iface and line.startswith("inet "):  # IPv4地址
                ip_part = line.split()[1]
                net_list[-1]["ips"].append({"type": "ipv4", "address": ip_part})
            elif current_iface and line.startswith("inet6 "):  # IPv6地址
                ip_part = line.split()[1]
                net_list[-1]["ips"].append({"type": "ipv6", "address": ip_part})
        return net_list if net_list else [{"error": self._get_msg("未检测到有效网卡信息", "No valid network interface detected")}]

    # ---------- 安全类信息 ----------
    def get_selinux_info(self) -> Dict:
        """获取SELinux状态（修复getenforce命令不存在问题）"""
        # 检查getenforce命令是否存在
        getenforce_path = self._find_cmd_absolute_path("getenforce")
        if getenforce_path:
            selinux_output = self._run_cmd_safe([getenforce_path])
            if selinux_output:
                return {"status": selinux_output.strip()}

        # 命令不存在时，通过配置文件判断
        logger.warning(self._get_msg("未找到getenforce命令，尝试通过配置文件判断SELinux状态", "getenforce not found, try to judge SELinux status from config"))
        try:
            with open("/etc/selinux/config", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SELINUX=") and not line.startswith("#"):
                        selinux_mode = line.split("=")[1].strip()
                        return {
                            "status": selinux_mode.upper(),
                            "note": self._get_msg("基于/etc/selinux/config配置判断", "Judged from /etc/selinux/config")
                        }
            return {"status": self._get_msg("未知", "Unknown"), "note": self._get_msg("未找到SELinux配置", "SELinux config not found")}
        except Exception as e:
            logger.error(self._get_msg(f"获取SELinux状态失败：{str(e)}", f"Failed to get SELinux status: {str(e)}"))
            return {"error": self._get_msg("获取SELinux状态失败", "Failed to get SELinux status")}

    def get_firewall_info(self) -> Dict:
        """获取防火墙规则（修复firewalld相关命令不存在问题）"""
        firewall_info = {}
        # 检查systemctl命令是否存在
        systemctl_path = self._find_cmd_absolute_path("systemctl")
        if not systemctl_path:
            logger.warning(self._get_msg("未找到systemctl命令，无法检查防火墙状态", "systemctl not found, cannot check firewall status"))
            firewall_info["status"] = self._get_msg("未知（无systemctl）", "Unknown (systemctl not found)")
            return firewall_info

        # 检查firewalld状态
        status_output = self._run_cmd_safe([systemctl_path, "is-active", "firewalld"])
        if status_output == "active":
            firewall_info["status"] = "active"
            # 检查firewall-cmd命令是否存在
            firewall_cmd_path = self._find_cmd_absolute_path("firewall-cmd")
            if firewall_cmd_path:
                ports_output = self._run_cmd_safe([firewall_cmd_path, "--list-ports"])
                firewall_info["open_ports"] = ports_output.strip().split() if ports_output and ports_output.strip() else []
            else:
                firewall_info["open_ports"] = [self._get_msg("firewall-cmd命令不存在，无法获取开放端口", "firewall-cmd not found, cannot get open ports")]
        elif status_output == "inactive":
            firewall_info["status"] = "inactive"
        else:
            # 未安装firewalld或命令执行失败
            firewall_info["status"] = self._get_msg("未安装firewalld或状态未知", "firewalld not installed or status unknown")
        return firewall_info

    # ---------- 批量采集多类型信息 ----------
    def collect_batch(self, info_types: List[InfoTypeEnum]) -> Dict[str, Dict]:
        """
        批量采集多类信息
        :param info_types: InfoTypeEnum列表
        :return: 结构化结果（key为信息类型字符串，value为对应采集结果）
        """
        batch_result = {}
        info_type_map = {
            InfoTypeEnum.OS: self.get_os_info,
            InfoTypeEnum.LOAD: self.get_load_info,
            InfoTypeEnum.UPTIME: self.get_uptime_info,
            InfoTypeEnum.CPU: self.get_cpu_info,
            InfoTypeEnum.MEM: self.get_mem_info,
            InfoTypeEnum.DISK: self.get_disk_info,
            InfoTypeEnum.GPU: self.get_gpu_info,
            InfoTypeEnum.NET: self.get_net_info,
            InfoTypeEnum.SELINUX: self.get_selinux_info,
            InfoTypeEnum.FIREWALL: self.get_firewall_info
        }
        for info_type in info_types:
            try:
                batch_result[info_type.value] = info_type_map[info_type]()
            except Exception as e:
                logger.error(self._get_msg(f"采集{info_type.value}信息失败：{str(e)}", f"Failed to collect {info_type.value} info: {str(e)}"))
                batch_result[info_type.value] = {"error": self._get_msg(f"采集{info_type.value}信息失败", f"Failed to collect {info_type.value} information")}
        return batch_result