import logging
import os
import subprocess
import re
from enum import Enum
from typing import Dict, List, Optional, Union
from config.public.base_config_loader import LanguageEnum, BaseConfig

# 初始化日志（仅保留基础配置）
logger = logging.getLogger("proc_tool")
logger.setLevel(logging.INFO)

# ========== 枚举类定义（不变，保留核心操作） ==========
class ProcActionEnum(str, Enum):
    LIST = "list"        # 所有进程
    FIND = "find"        # 按名称/PID查询
    STAT = "stat"        # 进程资源占用
    START = "start"      # 启动systemd服务
    RESTART = "restart"  # 重启systemd服务
    STOP = "stop"        # 停止systemd服务
    KILL = "kill"        # 强制终止进程

# ========== 通用工具函数（精简，保留必要功能） ==========
def get_language() -> LanguageEnum:
    return BaseConfig().get_config().public_config.language

def is_zh() -> bool:
    return get_language() == LanguageEnum.ZH

def init_result_dict(target_host: str = "127.0.0.1") -> Dict:
    """初始化返回结果（简洁格式）"""
    return {
        "success": False,
        "message": "",
        "result": {},
        "target": target_host,
        "proc_actions": []
    }

def parse_proc_actions(action_list: List[str]) -> List[ProcActionEnum]:
    """解析操作类型（仅保留必要校验）"""
    valid_values = [e.value for e in ProcActionEnum]
    if not action_list:
        msg = f"进程操作列表不能为空，可选值：{','.join(valid_values)}"
        raise ValueError(msg)

    parsed = []
    for action in action_list:
        action = action.strip().lower()
        if action not in valid_values:
            msg = f"无效操作：{action}，可选值：{','.join(valid_values)}"
            raise ValueError(msg)
        parsed.append(ProcActionEnum(action))
    return parsed

# ========== 核心工具函数（精简，无复杂嵌套） ==========
def get_cmd_path(cmd: str) -> Optional[str]:
    """获取命令绝对路径（简洁实现，避免复杂逻辑）"""
    # 优先遍历常见路径（OpenEuler默认路径）
    common_paths = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    for path in common_paths:
        cmd_path = os.path.join(path, cmd)
        if os.path.exists(cmd_path) and os.access(cmd_path, os.X_OK):
            return cmd_path
    # 路径不存在返回None
    logger.warning(f"命令不存在：{cmd}（未在常见路径中找到）")
    return None

def run_cmd(cmd: List[str]) -> Optional[str]:
    """执行命令（精简异常处理，只捕获关键错误）"""
    cmd_path = get_cmd_path(cmd[0])
    if not cmd_path:
        return None  # 命令不存在直接返回None
    cmd[0] = cmd_path  # 替换为绝对路径

    try:
        logger.info(f"执行命令：{' '.join(cmd)}")
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=True, timeout=10
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error(f"命令执行失败：{e.stderr.strip() or str(e)}")
        return None
    except Exception as e:
        logger.error(f"系统调用异常：{str(e)}")
        return None

# ========== 进程管理核心类（极简实现，易阅读） ==========
class ProcessManager:
    def __init__(self):
        self.zh = is_zh()  # 提前判断语言，避免重复调用

    def _msg(self, zh: str, en: str) -> str:
        """简洁多语言提示（直接返回对应语言）"""
        return zh if self.zh else en

    # ---------- 查：进程查询（核心功能，无多余嵌套） ----------
    def list_all_procs(self) -> List[Dict]:
        """列出所有进程（精简解析逻辑）"""
        output = run_cmd(["ps", "aux"])
        if not output:
            return [{"error": self._msg("ps命令执行失败", "ps command failed")}]

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) < 2:
            return [{"error": self._msg("无有效进程信息", "No valid process info")}]

        # 解析表头和数据
        headers = [h.lower() for h in lines[0].split()]
        procs = []
        for line in lines[1:]:
            parts = re.split(r"\s+", line, maxsplit=len(headers)-1)
            proc = dict(zip(headers, parts))
            # 只转换关键数字字段（避免复杂处理）
            for key in ["pid", "cpu", "mem"]:
                if key in proc:
                    proc[key] = float(proc[key]) if "." in proc[key] else int(proc[key])
            procs.append(proc)
        return procs

    def find_proc(self, name: Optional[str] = None, pid: Optional[int] = None) -> List[Dict]:
        """按名称/PID查询（避免管道符，简洁实现）"""
        if not (name or pid):
            return [{"error": self._msg("必须指定进程名称或PID", "Must specify proc name or PID")}]

        # 按PID查询
        if pid:
            output = run_cmd(["ps", "aux", "-p", str(pid)])
            return self._parse_ps_output(output) if output else []
        # 按名称查询（用ps+字符串过滤，避免grep管道）
        else:
            output = run_cmd(["ps", "aux"])
            if not output:
                return [{"error": self._msg("查询进程失败", "Failed to find process")}]
            procs = self._parse_ps_output(output)
            # 过滤目标进程（排除grep自身）
            return [p for p in procs if name.lower() in p.get("command", "").lower() and "grep" not in p.get("command", "")]

    def get_proc_stat(self, pid: int) -> Dict:
        """获取进程资源占用（精简参数校验和解析）"""
        if not isinstance(pid, int) or pid <= 0:
            return {"error": self._msg("PID必须为正整数", "PID must be positive integer")}

        output = run_cmd(["ps", "-p", str(pid), "-o", "pid,%cpu,%mem,rss,vsz,etime"])
        if not output:
            return {"error": self._msg(f"PID {pid} 不存在或查询失败", f"PID {pid} not found or query failed")}

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) < 2:
            return {"error": self._msg(f"PID {pid} 不存在", f"PID {pid} does not exist")}

        # 解析状态信息
        headers = [h.lower().replace("%", "pct") for h in lines[0].split()]
        parts = re.split(r"\s+", lines[1])
        stat = dict(zip(headers, parts))
        # 转换数字字段
        for key in ["pid", "cpupct", "mempct", "rss", "vsz"]:
            if key in stat:
                stat[key] = float(stat[key]) if "." in stat[key] else int(stat[key])
        return stat

    # ---------- 启/停/重启：systemd服务操作（简洁实现） ----------
    def _service_op(self, action: str, service_name: str) -> Dict:
        """统一处理systemd服务操作（减少重复代码）"""
        if not service_name:
            return {"error": self._msg("必须指定服务名称", "Must specify service name")}

        output = run_cmd(["systemctl", action, service_name])
        if output is not None:
            return {"message": self._msg(f"服务 {service_name} {action} 成功", f"Service {service_name} {action} success")}
        else:
            return {"error": self._msg(f"服务 {service_name} {action} 失败", f"Service {service_name} {action} failed")}

    def start_proc(self, service_name: str) -> Dict:
        return self._service_op("start", service_name)

    def restart_proc(self, service_name: str) -> Dict:
        return self._service_op("restart", service_name)

    def stop_proc(self, service_name: str) -> Dict:
        return self._service_op("stop", service_name)

    # ---------- 强制终止进程（简洁实现） ----------
    def kill_proc(self, pid: int) -> Dict:
        if not isinstance(pid, int) or pid <= 0:
            return {"error": self._msg("PID必须为正整数", "PID must be positive integer")}

        # 先尝试正常终止，失败则强制终止（无嵌套try）
        output = run_cmd(["kill", str(pid)])
        if output is not None:
            return {"message": self._msg(f"已向PID {pid} 发送终止信号", f"Termination signal sent to PID {pid}")}

        output = run_cmd(["kill", "-9", str(pid)])
        if output is not None:
            return {"message": self._msg(f"已强制终止PID {pid}", f"Forcibly terminated PID {pid}")}
        else:
            return {"error": self._msg(f"终止PID {pid} 失败", f"Failed to terminate PID {pid}")}

    # ---------- 辅助函数（精简） ----------
    def _parse_ps_output(self, output: str) -> List[Dict]:
        """解析ps输出（无多余逻辑）"""
        if not output:
            return []
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) < 2:
            return []
        headers = [h.lower() for h in lines[0].split()]
        return [dict(zip(headers, re.split(r"\s+", line, maxsplit=len(headers)-1))) for line in lines[1:]]

    # ---------- 批量执行（精简校验和执行逻辑） ----------
    def exec_batch(
            self,
            actions: List[ProcActionEnum],
            proc_name: Optional[str] = None,
            pid: Optional[int] = None,
            service_name: Optional[str] = None
    ) -> Dict[str, Union[List[Dict], Dict]]:
        batch_result = {}
        # 操作映射（减少if-else）
        action_map = {
            ProcActionEnum.LIST: self.list_all_procs,
            ProcActionEnum.FIND: lambda: self.find_proc(name=proc_name, pid=pid),
            ProcActionEnum.STAT: lambda: self.get_proc_stat(pid=pid),
            ProcActionEnum.START: lambda: self.start_proc(service_name=service_name),
            ProcActionEnum.RESTART: lambda: self.restart_proc(service_name=service_name),
            ProcActionEnum.STOP: lambda: self.stop_proc(service_name=service_name),
            ProcActionEnum.KILL: lambda: self.kill_proc(pid=pid)
        }

        # 执行每个操作（无复杂嵌套）
        for action in actions:
            try:
                batch_result[action.value] = action_map[action]()
            except Exception as e:
                batch_result[action.value] = {"error": str(e)}
                logger.error(f"操作 {action.value} 失败：{str(e)}")

        return batch_result