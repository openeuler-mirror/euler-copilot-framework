import subprocess
from typing import Any, Dict, Optional
import paramiko

from servers.oe_cli_mcp_server.config.base_config_loader import LanguageEnum


def _format_gpu_info(raw_info: Dict[str, Any],
                     host: str, include_processes: bool, lang: Optional[LanguageEnum]) -> Dict[str, Any]:
    """格式化输出（双语适配描述）"""
    no_process_msg = "未开启进程查询（需设置include_processes=True）" if lang == LanguageEnum.ZH else "Process query not enabled (set include_processes=True)"
    return {
        "host": host,
        "gpu_count": len(raw_info["gpu"]),
        "gpu_details": raw_info["gpu"],
        "include_processes": include_processes,
        "process_details": raw_info["processes"] if include_processes else no_process_msg
    }
    
def _get_local_gpu_status(gpu_index: Optional[int], include_processes: bool, lang: Optional[LanguageEnum]) -> Dict[str, Any]:
    """本地GPU查询（双语错误提示）"""
    try:
        # 构建基础查询命令
        cmd = "/usr/bin/nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits"
        if gpu_index is not None:
            cmd += f" -i {gpu_index}"

        # 执行本地命令
        result = subprocess.run(
            cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8"
        )

        # 解析GPU信息
        gpu_info = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                idx, name, mem_used, mem_total, gpu_util = line.split(', ')
                gpu_info.append({
                    "index": int(idx),
                    "name": name.strip(),
                    "memory_used": int(mem_used),
                    "memory_total": int(mem_total),
                    "gpu_utilization": int(gpu_util)
                })
            except ValueError:
                # 解析行数据失败（双语提示）
                warn_msg = f"跳过无效的GPU信息行: {line}" if lang == LanguageEnum.ZH else f"Skipping invalid GPU info line: {line}"
                print(warn_msg)  # 或使用logger
                continue

        # 处理进程信息
        proc_info = []
        if include_processes:
            proc_cmd = "/usr/bin/nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader,nounits"
            try:
                proc_result = subprocess.run(
                    proc_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8"
                )
                for line in proc_result.stdout.strip().split('\n'):
                    if not line:
                        continue
                    try:
                        pid, proc_name, used_mem = line.split(', ')
                        proc_info.append({
                            "pid": int(pid),
                            "name": proc_name.strip(),
                            "used_memory": int(used_mem)
                        })
                    except ValueError:
                        # 进程信息解析失败（双语提示）
                        warn_msg = f"跳过无效的进程信息行: {line}" if lang == LanguageEnum.ZH else f"Skipping invalid process info line: {line}"
                        print(warn_msg)
                        continue
            except subprocess.CalledProcessError as e:
                # 进程查询命令执行失败（双语提示）
                err_msg = f"查询GPU进程信息失败: {e.stderr}" if lang == LanguageEnum.ZH else f"Failed to query GPU process info: {e.stderr}"
                raise RuntimeError(err_msg)

        return {"gpu": gpu_info, "processes": proc_info}

    except FileNotFoundError:
        # 未找到nvidia-smi命令（双语提示）
        err_msg = "未找到nvidia-smi命令，请确认已安装NVIDIA驱动" if lang == LanguageEnum.ZH else "/usr/bin/nvidia-smi command not found, please ensure NVIDIA driver is installed"
        raise RuntimeError(err_msg)
    except subprocess.CalledProcessError as e:
        # GPU基础查询失败（双语提示）
        err_msg = f"执行GPU查询命令失败: {e.stderr}" if lang == LanguageEnum.ZH else f"Failed to execute GPU query command: {e.stderr}"
        raise RuntimeError(err_msg)


def _get_remote_gpu_status_via_ssh(ssh: paramiko.SSHClient, gpu_index: Optional[int],
                                   include_processes: bool, lang: Optional[LanguageEnum]) -> Dict[str, Any]:
    """远程GPU查询（双语错误提示）"""
    # 1. 查询GPU基础信息
    cmd = "/usr/bin/nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits"
    if gpu_index is not None:
        cmd += f" -i {gpu_index}"

    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    error = stderr.read().decode("utf-8").strip()

    if exit_status != 0:
        # 远程命令执行失败（双语提示）
        if "command not found" in error:
            err_msg = "远程主机未找到nvidia-smi命令，可能未安装NVIDIA驱动" if lang == LanguageEnum.ZH else "/usr/bin/nvidia-smi command not found on remote host, possibly no NVIDIA driver installed"
        else:
            err_msg = f"远程GPU查询命令执行失败: {error}" if lang == LanguageEnum.ZH else f"Remote GPU query command failed: {error}"
        raise RuntimeError(err_msg)

    # 解析GPU信息
    gpu_info = []
    for line in stdout.read().decode("utf-8").strip().split('\n'):
        if not line:
            continue
        try:
            idx, name, mem_used, mem_total, gpu_util = line.split(', ')
            gpu_info.append({
                "index": int(idx),
                "name": name.strip(),
                "memory_used": int(mem_used),
                "memory_total": int(mem_total),
                "gpu_utilization": int(gpu_util)
            })
        except ValueError:
            warn_msg = f"跳过远程无效的GPU信息行: {line}" if lang == LanguageEnum.ZH else f"Skipping invalid remote GPU info line: {line}"
            print(warn_msg)
            continue

    # 2. 查询进程信息（按需）
    proc_info = []
    if include_processes:
        proc_cmd = "/usr/bin/nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader,nounits"
        stdin_proc, stdout_proc, stderr_proc = ssh.exec_command(proc_cmd)
        exit_status_proc = stdout_proc.channel.recv_exit_status()
        error_proc = stderr_proc.read().decode("utf-8").strip()

        if exit_status_proc != 0:
            err_msg = f"远程GPU进程查询失败: {error_proc}" if lang == LanguageEnum.ZH else f"Remote GPU process query failed: {error_proc}"
            raise RuntimeError(err_msg)

        for line in stdout_proc.read().decode("utf-8").strip().split('\n'):
            if not line:
                continue
            try:
                pid, proc_name, used_mem = line.split(', ')
                proc_info.append({
                    "pid": int(pid),
                    "name": proc_name.strip(),
                    "used_memory": int(used_mem)
                })
            except ValueError:
                warn_msg = f"跳过远程无效的进程信息行: {line}" if lang == LanguageEnum.ZH else f"Skipping invalid remote process info line: {line}"
                print(warn_msg)
                continue

    return {"gpu": gpu_info, "processes": proc_info}