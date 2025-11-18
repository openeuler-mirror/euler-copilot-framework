from typing import Union, List, Dict
import platform
import os
import paramiko
import yaml
import datetime
import subprocess
from typing import Any, Dict
import psutil
import socket
from datetime import datetime
from mcp.server import FastMCP
import telnetlib
from config.public.base_config_loader import LanguageEnum
from config.private.remote_info.config_loader import RemoteInfoConfig
mcp = FastMCP("Remote info MCP Server", host="0.0.0.0", port=RemoteInfoConfig().get_config().private_config.port)


@mcp.tool(
    name="top_collect_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    "top_collect_tool",
    description='''
    使用top命令获取远端机器或者本机内存占用最多的k个进程
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示获取本机的top k进程
        - k: 需要获取的进程数量，默认为5，可根据实际需求调整
    2. 返回值为包含进程信息的字典列表，每个字典包含以下键
        - pid: 进程ID
        - name: 进程名称
        - memory: 内存使用量（单位MB）
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Use the top command to get the top k memory-consuming processes on a remote machine or the local machine.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the top k processes of the local machine.
        - k: The number of processes to be obtained, the default is 5, which can be adjusted according to actual needs.
    2. The return value is a list of dictionaries containing process information, each dictionary contains
        the following keys:
        - pid: Process ID
        - name: Process name
        - memory: Memory usage (in MB)
    '''

)
def top_collect_tool(host: Union[str, None] = None, k: int = 5) -> List[Dict[str, Any]]:
    """使用top命令获取内存占用最多的k个进程"""
    if host is None:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                memory_usage = proc.info['memory_info'].rss / (1024 * 1024)  # 转换为MB
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'memory': memory_usage
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 按内存使用量排序并取前k个
        processes.sort(key=lambda x: x['memory'], reverse=True)
        return processes[:k]
    else:
        for host_config in RemoteInfoConfig().get_config().public_config.remote_hosts:
            if host == host_config.name or host == host_config.host:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    hostname=host_config.host,
                    port=host_config.port,
                    username=host_config.username,
                    password=host_config.password
                )
                stdin, stdout, stderr = ssh.exec_command(f"ps aux --sort=-%mem | head -n {k + 1}")
                output = stdout.read().decode()
                ssh.close()

                lines = output.strip().split('\n')[1:]
                processes = []
                for line in lines:
                    parts = line.split()
                    pid = int(parts[1])
                    name = parts[10]
                    memory = float(parts[3]) * psutil.virtual_memory().total / (1024 * 1024)  # 转换为MB
                    processes.append({
                        'pid': pid,
                        'name': name,
                        'memory': memory
                    })
                return processes
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError(f"未找到远程主机: {host}")
        else:
            raise ValueError(f"Remote host not found: {host}")


@mcp.tool(
    name="get_process_info_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "get_process_info_tool",
    description='''
    获取指定PID的进程详细信息
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示
            获取本机的指定PID进程信息
        - pid: 需要获取信息的进程ID
    2. 返回值为包含进程详细信息的字典，包含以下键
        - pid: 进程ID
        - name: 进程名称
        - status: 进程状态
        - create_time: 进程创建时间
        - cpu_times: CPU时间信息
        - memory_info: 内存使用信息
        - open_files: 打开的文件列表
        - connections: 网络连接信息
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get detailed information of the process with the specified PID.
    1. Input values are as follows:

        - host: Remote host name or IP address. If not provided, it means to get
            the specified PID process information of the local machine.
        - pid: The process ID for which information is to be obtained.
    2. The return value is a dictionary containing detailed information of the process,
        containing the following keys:
        - pid: Process ID
        - name: Process name
        - status: Process status
        - create_time: Process creation time
        - cpu_times: CPU time information
        - memory_info: Memory usage information
        - open_files: List of opened files
        - connections: Network connection information
    '''
)
def get_process_info_tool(host: Union[str, None] = None, pid: int = 0) -> Dict[str, Any]:
    """获取指定PID的进程详细信息"""
    if pid <= 0:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError("PID必须为正整数")
        else:
            raise ValueError("PID must be a positive integer")
    if host is None:
        try:
            proc = psutil.Process(pid)
            process_info = {
                'pid': proc.pid,
                'name': proc.name(),
                'status': proc.status(),
                'create_time': datetime.fromtimestamp(proc.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
                'cpu_times': proc.cpu_times()._asdict(),
                'memory_info': proc.memory_info()._asdict(),
                'open_files': [f._asdict() for f in proc.open_files()],
                'connections': [c._asdict() for c in proc.connections()]
            }
            return process_info
        except psutil.NoSuchProcess:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到PID为{pid}的进程")
            else:
                raise ValueError(f"Process with PID {pid} not found")
    else:
        for host_config in RemoteInfoConfig().get_config().public_config.remote_hosts:
            if host == host_config.name or host == host_config.host:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    hostname=host_config.host,
                    port=host_config.port,
                    username=host_config.username,
                    password=host_config.password
                )

                # 分别获取各项信息
                commands = {
                    'name': f"ps -p {pid} -o comm=",
                    'status': f"ps -p {pid} -o state=",
                    'create_time': f"ps -p {pid} -o lstart=",
                    'cpu_times': f"ps -p {pid} -o cputime=",
                    'memory_info': f"ps -p {pid} -o rss=",
                    'open_files': f"lsof -p {pid}",
                    'connections': f"netstat -tunap | grep {pid}"
                }
                process_info = {'pid': pid}
                for key, cmd in commands.items():
                    try:
                        stdin, stdout, stderr = ssh.exec_command(cmd)
                        output = stdout.read().decode().strip()
                        if key == 'create_time':
                            process_info[key] = output
                        elif key == 'cpu_times':
                            process_info[key] = output
                        elif key == 'memory_info':
                            process_info[key] = int(output) / 1024  # 转换为MB
                        elif key == 'open_files':
                            files = output.split('\n')[1:]
                            process_info[key] = files
                        elif key == 'connections':
                            conns = output.split('\n')
                            process_info[key] = conns
                        else:
                            process_info[key] = output
                    except Exception as e:
                        process_info[key] = f"Error retrieving {key}: {e}"
                ssh.close()
                return process_info


@mcp.tool(
    name="change_name_to_pid_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "change_name_to_pid_tool",
    description='''
    根据进程名称获取对应的PID列表
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示
            获取本机的指定名称进程的PID列表
        - name: 需要获取PID的进程名称
    2. 返回值为包含对应PID的字符串，每个PID之间以空格分隔
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get the list of PIDs corresponding to the process name.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the PID list of the specified name process of the local machine.
        - name: The process name for which the PID is to be obtained.
    2. The return value is a string containing the corresponding PIDs, with each PID separated by a space.
    '''
)
def change_name_to_pid_tool(host: Union[str, None] = None, name: str = "") -> List[int]:
    """根据进程名称获取对应的PID列表"""
    if not name:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError("进程名称不能为空")
        else:
            raise ValueError("Process name cannot be empty")
    pids = []
    if host is None:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == name:
                pids.append(str(proc.info['pid']))
        return ' '.join(pids)
    else:
        for host_config in RemoteInfoConfig().get_config().public_config.remote_hosts:
            if host == host_config.name or host == host_config.host:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    hostname=host_config.host,
                    port=host_config.port,
                    username=host_config.username,
                    password=host_config.password
                )
                stdin, stdout, stderr = ssh.exec_command(f"pgrep {name}")
                output = stdout.read().decode().strip()
                ssh.close()
                if output:
                    pids = [str(pid) for pid in output.split('\n')]
                return ' '.join(pids)
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError(f"未找到远程主机: {host}")
        else:
            raise ValueError(f"Remote host not found: {host}")


@mcp.tool(
    name="get_cpu_info_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "get_cpu_info_tool",
    description='''
    获取CPU信息
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示获取本机的CPU信息
    2. 返回值为包含CPU信息的字典，包含以下键
        - physical_cores: 物理核心数
        - total_cores: 逻辑核心数
        - max_frequency: 最大频率（MHz）
        - min_frequency: 最小频率（MHz）
        - current_frequency: 当前频率（MHz）
        - cpu_usage: 每个核心的使用率（百分比）
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get CPU information.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the CPU information of the local machine.
    2. The return value is a dictionary containing CPU information, containing the following
        keys:
        - physical_cores: Number of physical cores
        - total_cores: Number of logical cores
        - max_frequency: Maximum frequency (MHz)
        - min_frequency: Minimum frequency (MHz)
        - current_frequency: Current frequency (MHz)
        - cpu_usage: Usage rate of each core (percentage)
    '''
)
def get_cpu_info_tool(host: Union[str, None] = None) -> Dict[str, Any]:
    """获取CPU信息"""
    if host is None:
        # 获取本地CPU信息
        try:
            cpu_freq = psutil.cpu_freq()
            cpu_info = {
                'physical_cores': psutil.cpu_count(logical=False),
                'total_cores': psutil.cpu_count(logical=True),
                'max_frequency': cpu_freq.max if cpu_freq else None,
                'min_frequency': cpu_freq.min if cpu_freq else None,
                'current_frequency': cpu_freq.current if cpu_freq else None,
                'cpu_usage': psutil.cpu_percent(percpu=True)
            }
            return cpu_info
        except Exception as e:
            return {"error": f"获取本地CPU信息失败: {str(e)}"}
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            # 定义获取信息的命令，增加兼容性和容错性
            commands = {
                'physical_cores': "grep '^processor' /proc/cpuinfo | sort -u | wc -l",
                'total_cores': "nproc --all",
                'max_frequency': "grep 'cpu MHz' /proc/cpuinfo | head -1 | awk '{print $4}'",
                'min_frequency': "grep 'cpu MHz' /proc/cpuinfo | tail -1 | awk '{print $4}'",  # 近似值
                'current_frequency': "grep 'cpu MHz' /proc/cpuinfo | head -1 | awk '{print $4}'",
                'cpu_usage': "mpstat -P ALL 1 1 | awk '/^Average/ && $2 != \"all\" {print $3 + $4 + $5}'"
            }

            cpu_info = {}
            for key, cmd in commands.items():
                try:
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
                    error = stderr.read().decode().strip()
                    output = stdout.read().decode().strip()

                    if error:
                        print(f"Command {cmd} error: {error}")

                    if not output:
                        cpu_info[key] = None
                        continue

                    # 转换输出格式
                    if key in ['physical_cores', 'total_cores']:
                        cpu_info[key] = int(output)
                    elif key in ['max_frequency', 'min_frequency', 'current_frequency']:
                        cpu_info[key] = float(output)
                    elif key == 'cpu_usage':
                        # 处理每个核心的使用率
                        cpu_info[key] = [float(val) for val in output.split('\n') if val]

                except Exception as e:
                    cpu_info[key] = f"获取{key}失败: {str(e)}"

            return cpu_info

        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程CPU信息失败: {str(e)}")
        finally:
            # 确保SSH连接关闭
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


@mcp.tool(
    name="memory_anlyze_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "memory_anlyze_tool",
    description='''
    分析内存使用情况
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示获取本机的内存使用情况
    2. 返回值为包含内存使用情况的字典，包含以下键
        - total: 总内存（MB）
        - available: 可用内存（MB）
        - used: 已用内存（MB）
        - free: 空闲内存（MB）
        - percent: 内存使用率（百分比）
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Analyze memory usage.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the memory usage of the local machine.
    2. The return value is a dictionary containing memory usage, containing the following
        keys:
        - total: Total memory (MB)
        - available: Available memory (MB)
        - used: Used memory (MB)
        - free: Free memory (MB)
        - percent: Memory usage rate (percentage)
    '''
)
def memory_anlyze_tool(host: Union[str, None] = None) -> Dict[str, Any]:
    """分析内存使用情况"""
    if host is None:
        # 获取本地内存信息
        try:
            mem = psutil.virtual_memory()
            memory_info = {
                'total': mem.total / (1024 * 1024),       # 转换为MB
                'available': mem.available / (1024 * 1024),  # 转换为MB
                'used': mem.used / (1024 * 1024),         # 转换为MB
                'free': mem.free / (1024 * 1024),         # 转换为MB
                'percent': mem.percent
            }
            return memory_info
        except Exception as e:
            return {"error": f"获取本地内存信息失败: {str(e)}"}
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            # 使用free命令获取内存信息，增加兼容性和容错性
            cmd = "free -m"
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            error = stderr.read().decode().strip()
            output = stdout.read().decode().strip()

            if error:
                raise ValueError(f"Command {cmd} error: {error}")

            if not output:
                raise ValueError("未能获取内存信息")

            lines = output.split('\n')
            if len(lines) < 2:
                raise ValueError("内存信息格式异常")
            mem_values = lines[1].split()
            if len(mem_values) < 7:
                raise ValueError("内存信息数据不完整")
            memory_info = {
                'total': float(mem_values[1]),      # 已经是MB
                'used': float(mem_values[2]),       # 已经是MB
                'free': float(mem_values[3]),       # 已经是MB
                'shared': float(mem_values[4]),     # 已经是MB
                'buff_cache': float(mem_values[5]),  # 已经是MB
                'available': float(mem_values[6]),  # 已经是MB
                'percent': (float(mem_values[2]) / float(mem_values[1])) * 100 if float(mem_values[1]) > 0 else 0
            }
            return memory_info
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程内存信息失败: {str(e)}")
        finally:
            # 确保SSH连接关闭
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


@mcp.tool(
    name="get_disk_info_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "get_disk_info_tool",
    description='''
    获取磁盘信息
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示获取本机的磁盘信息
    2. 返回值为包含磁盘信息的字典，包含以下键
        - device: 设备名称
        - mountpoint: 挂载点
        - fstype: 文件系统类型
        - total: 总容量（GB）
        - used: 已用容量（GB）
        - free: 可用容量（GB）
        - percent: 使用率（百分比）
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get disk information.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the disk information of the local machine.
    2. The return value is a list of dictionaries containing disk information, each dictionary contains
        the following keys:
        - device: Device name
        - mountpoint: Mount point
        - fstype: File system type
        - total: Total capacity (GB)
        - used: Used capacity (GB)
        - free: Free capacity (GB)
        - percent: Usage rate (percentage)
    '''
)
def get_disk_info_tool(host: Union[str, None] = None) -> List[Dict[str, Any]]:
    """获取磁盘信息"""
    if host is None:
        # 获取本地磁盘信息
        try:
            partitions = psutil.disk_partitions()
            disk_info = []
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disk_info.append({
                        'device': part.device,
                        'mountpoint': part.mountpoint,
                        'fstype': part.fstype,
                        'total': usage.total / (1024 * 1024 * 1024),  # 转换为GB
                        'used': usage.used / (1024 * 1024 * 1024),    # 转换为GB
                        'free': usage.free / (1024 * 1024 * 1024),    # 转换为GB
                        'percent': usage.percent
                    })
                except PermissionError:
                    continue
            return disk_info
        except Exception as e:
            return {"error": f"获取本地磁盘信息失败: {str(e)}"}
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            # 使用df命令获取磁盘信息，增加兼容性和容错性
            cmd = "df -h"
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            error = stderr.read().decode().strip()
            output = stdout.read().decode().strip()
            if error:
                raise ValueError(f"Command {cmd} error: {error}")
            if not output:
                raise ValueError("未能获取磁盘信息")
            lines = output.split('\n')[1:]
            disk_info = []
            for line in lines:
                parts = line.split()
                if len(parts) < 7:
                    continue
                disk_info.append({
                    'device': parts[0],
                    'mountpoint': parts[1],
                    'fstype': parts[2],
                    'total': float(parts[3][:-1]) if parts[3][-1] == 'G' else 0,  # 仅处理GB单位
                    'used': float(parts[4][:-1]) if parts[4][-1] == 'G' else 0,   # 仅处理GB单位
                    'free': float(parts[5][:-1]) if parts[5][-1] == 'G' else 0,   # 仅处理GB单位
                    'percent': float(parts[6][:-1]) if parts[6][-1] == '%' else 0
                })
            return disk_info
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程磁盘信息失败: {str(e)}")
        finally:
            # 确保SSH连接关闭
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


@mcp.tool(
    name="get_os_info_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "get_os_info_tool",
    description='''
    获取操作系统信息
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示获取本机的操作系统信息
    2. 返回值为字符串，包含操作系统类型和版本信息
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get operating system information.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the operating system information of the local machine.
    2. The return value is a string containing the operating system type and version information.
    '''
)
def get_os_info_tool(host: Union[str, None] = None) -> str:
    if host is None:
        # 获取本地操作系统信息
        try:
            os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
            return os_info
        except Exception as e:
            return f"获取本地操作系统信息失败: {str(e)}"
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            # 使用uname命令获取操作系统信息，增加兼容性和容错性
            if target_host.os_type.lower() == "openeuler":
                cmd = "cat /etc/openEuler-release"
            elif target_host.os_type.lower() == "hce":
                cmd = "cat /etc/hce-release"
            elif target_host.os_type.lower() == "ubuntu":
                cmd = "lsb_release -a"
            elif target_host.os_type.lower() == "centos":
                cmd = "cat /etc/centos-release"
            elif target_host.os_type.lower() == "debian":
                cmd = "cat /etc/debian_version"
            elif target_host.os_type.lower() == "redhat":
                cmd = "cat /etc/redhat-release"
            else:
                cmd = "uname -a"
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            error = stderr.read().decode().strip()
            output = stdout.read().decode().strip()
            if error:
                raise ValueError(f"Command {cmd} error: {error}")
            if not output:
                raise ValueError("未能获取操作系统信息")
            return output
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程操作系统信息失败: {str(e)}")
        finally:
            # 确保SSH连接关闭
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


@mcp.tool(
    name="get_network_info_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "get_network_info_tool",
    description='''
    获取网络接口信息
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示获取本机的网络接口信息
    2. 返回值为包含网络接口信息的字典列表，每个字典包含以下键
        - interface: 接口名称
        - ip_address: IP地址
        - netmask: 子网掩码
        - mac_address: MAC地址
        - is_up: 接口是否启用（布尔值）
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get network interface information.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the network interface information of the local machine.
    2. The return value is a list of dictionaries containing network interface information,
        each dictionary contains the following keys:
        - interface: Interface name
        - ip_address: IP address
        - netmask: Netmask
        - mac_address: MAC address
        - is_up: Whether the interface is up (boolean)
    '''
)
def get_network_info_tool(host: Union[str, None] = None) -> List[Dict[str, Any]]:
    """获取网络接口信息"""
    if host is None:
        # 获取本地网络接口信息
        try:
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            network_info = []
            for interface, addrs in net_if_addrs.items():
                ip_address = None
                netmask = None
                mac_address = None
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip_address = addr.address
                        netmask = addr.netmask
                    elif addr.family == psutil.AF_LINK:
                        mac_address = addr.address
                is_up = net_if_stats[interface].isup if interface in net_if_stats else False
                network_info.append({
                    'interface': interface,
                    'ip_address': ip_address,
                    'netmask': netmask,
                    'mac_address': mac_address,
                    'is_up': is_up
                })
            return network_info
        except Exception as e:
            return {"error": f"获取本地网络接口信息失败: {str(e)}"}
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            # 使用ip命令获取网络接口信息，增加兼容性和容错性
            cmd = "ip -o addr show"
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            error = stderr.read().decode().strip()
            output = stdout.read().decode().strip()
            if error:
                raise ValueError(f"Command {cmd} error: {error}")
            if not output:
                raise ValueError("未能获取网络接口信息")
            lines = output.split('\n')
            network_info = []
            for line in lines:
                parts = line.split()
                if len(parts) < 4:
                    continue
                interface = parts[1]
                ip_address = None
                netmask = None
                if parts[2] == 'inet':
                    ip_address = parts[3].split('/')[0]
                    netmask = parts[3].split('/')[1]
                mac_address = None
                is_up = False
                # 获取MAC地址和接口状态
                cmd_mac = f"cat /sys/class/net/{interface}/address"
                stdin_mac, stdout_mac, stderr_mac = ssh.exec_command(cmd_mac, timeout=5)
                mac_output = stdout_mac.read().decode().strip()
                if mac_output:
                    mac_address = mac_output
                cmd_state = f"cat /sys/class/net/{interface}/operstate"
                stdin_state, stdout_state, stderr_state = ssh.exec_command(cmd_state, timeout=5)
                state_output = stdout_state.read().decode().strip()
                if state_output == 'up':
                    is_up = True
                network_info.append({
                    'interface': interface,
                    'ip_address': ip_address,
                    'netmask': netmask,
                    'mac_address': mac_address,
                    'is_up': is_up
                })
            return network_info
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程网络接口信息失败: {str(e)}")
        finally:
            # 确保SSH连接关闭
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


@mcp.tool(
    name="write_report_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "write_report_tool",
    description='''
    将分析结果写入报告文件
    1. 输入值如下：
        - report: 报告内容字符串
    2. 返回值为写入报告文件的路径字符串
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Write analysis results to a report file.
    1. Input values are as follows:
        - report: Report content string
    2. The return value is the path string of the written report file.
    '''
)
def write_report_tool(report: str) -> str:
    """将分析结果写入报告文件"""
    if not report:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError("报告内容不能为空")
        else:
            raise ValueError("Report content cannot be empty")
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
        report_path = f"system_report_{timestamp}.txt"
        with open(report_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(report)
        real_path = os.path.realpath(report_path)
        return real_path
    except Exception as e:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError(f"写入报告文件失败: {str(e)}")
        else:
            raise ValueError(f"Failed to write report file: {str(e)}")


@mcp.tool(
    name="telnet_test_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "telnet_test_tool",
    description='''
    测试Telnet连接
    1. 输入值如下：
        - host: 远程主机名称或IP地址
        - port: 端口号
    2. 返回值为布尔值，表示连接是否成功
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Test Telnet connection.
    1. Input values are as follows:
        - host: Remote host name or IP address
        - port: Port number
    2. The return value is a boolean indicating whether the connection was successful.
    '''
)
def telnet_test_tool(host: str, port: int) -> bool:
    """测试Telnet连接"""
    if not host:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError("主机不能为空")
        else:
            raise ValueError("Host cannot be empty")
    if port <= 0 or port > 65535:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError("端口号必须在1到65535之间")
        else:
            raise ValueError("Port number must be between 1 and 65535")
    try:
        with telnetlib.Telnet(host, port, timeout=5) as tn:
            return True
    except Exception as e:
        print(f"Telnet连接失败: {str(e)}")
        return False


@mcp.tool(
    name="ping_test_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "ping_test_tool",
    description='''
    测试Ping连接
    1. 输入值如下：
        - host: 远程主机名称或IP地址
    2. 返回值为布尔值，表示连接是否成功
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Test Ping connection.
    1. Input values are as follows:
        - host: Remote host name or IP address
    2. The return value is a boolean indicating whether the connection was successful.
    '''
)
def ping_test_tool(host: str) -> bool:
    """测试Ping连接"""
    if not host:
        if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError("主机不能为空")
        else:
            raise ValueError("Host cannot be empty")
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', host]
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ping连接失败: {str(e)}")
        return False


@mcp.tool(
    name="get_dns_info_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "get_dns_info_tool",
    description='''
    获取DNS配置信息
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示
    获取本机的DNS配置信息
    2. 返回值为包含DNS配置信息的字典，包含以下
        键
        - nameservers: DNS服务器列表
        - search: 搜索域列表
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Get DNS configuration information.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to get
            the DNS configuration information of the local machine.
    2. The return value is a dictionary containing DNS configuration information, containing the following
        keys:
        - nameservers: List of DNS servers
        - search: List of search domains
    '''
)
def get_dns_info_tool(host: Union[str, None] = None) -> Dict[str, Any]:
    """获取DNS配置信息"""
    if host is None:
        # 获取本地DNS信息
        try:
            dns_info = {'nameservers': [], 'search': []}
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        dns_info['nameservers'].append(line.split()[1])
                    elif line.startswith('search'):
                        dns_info['search'].extend(line.split()[1:])
            return dns_info
        except Exception as e:
            return {"error": f"获取本地DNS信息失败: {str(e)}"}
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            # 使用cat命令获取DNS信息，增加兼容性和容错性
            cmd = "cat /etc/resolv.conf"
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            error = stderr.read().decode().strip()
            output = stdout.read().decode().strip()
            if error:
                raise ValueError(f"Command {cmd} error: {error}")
            if not output:
                raise ValueError("未能获取DNS信息")
            dns_info = {'nameservers': [], 'search': []}
            for line in output.split('\n'):
                if line.startswith('nameserver'):
                    dns_info['nameservers'].append(line.split()[1])
                elif line.startswith('search'):
                    dns_info['search'].extend(line.split()[1:])
            return dns_info
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程DNS信息失败: {str(e)}")
        finally:
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


@mcp.tool(
    name="perf_data_tool"
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else "perf_data_tool",
    description='''
    收集性能数据
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示收集本机的性能数据
        - pid : 进程ID，若不提供则表示收集所有进程的性能数据
    2. 返回值为包含性能数据的字典，包含以下键
        - cpu_usage: CPU使用率（百分比）
        - memory_usage: 内存使用率（百分比）
        - io_counters: I/O统计信息（字典）
    '''
    if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Collect performance data.
    1. Input values are as follows:
        - host: Remote host name or IP address. If not provided, it means to collect
            the performance data of the local machine.
        - pid : Process ID. If not provided, it means to collect performance data for all processes.
    2. The return value is a dictionary containing performance data, containing the following
        keys:
        - cpu_usage: CPU usage (percentage)
        - memory_usage: Memory usage (percentage)
        - io_counters: I/O statistics (dictionary)
    '''
)
def perf_data_tool(host: Union[str, None] = None, pid: Union[int, None] = None) -> Dict[str, Any]:
    """收集性能数据"""
    if host is None:
        # 获取本地性能数据
        try:
            if pid is not None:
                # 获取指定进程的性能数据
                proc = psutil.Process(pid)
                cpu_usage = proc.cpu_percent(interval=1)
                memory_info = proc.memory_info()
                memory_usage = proc.memory_percent()
                io_counters = proc.io_counters()._asdict() if hasattr(proc, 'io_counters') else {}
            else:
                # 获取所有进程的性能数据
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()
                memory_usage = memory_info.percent
                io_counters = {}
            performance_data = {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'io_counters': io_counters
            }
            return performance_data
        except psutil.NoSuchProcess:
            return {"error": f"进程ID {pid} 不存在"}
        except Exception as e:
            return {"error": f"获取本地性能数据失败: {str(e)}"}
    else:
        # 查找远程主机配置
        remote_hosts = RemoteInfoConfig().get_config().public_config.remote_hosts
        target_host = next(
            (h for h in remote_hosts if host == h.name or host == h.host),
            None
        )

        if not target_host:
            if RemoteInfoConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")

        ssh = None
        try:
            # 建立SSH连接
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=target_host.host,
                port=target_host.port,
                username=target_host.username,
                password=target_host.password,
                timeout=10,
                banner_timeout=10
            )

            if pid is not None:
                # 获取指定进程的性能数据
                cmd_cpu = f"ps -p {pid} -o %cpu --no-headers"
                cmd_mem = f"ps -p {pid} -o %mem --no-headers"
                cmd_io = f"cat /proc/{pid}/io"
                stdin_cpu, stdout_cpu, stderr_cpu = ssh.exec_command(cmd_cpu, timeout=5)
                stdin_mem, stdout_mem, stderr_mem = ssh.exec_command(cmd_mem, timeout=5)
                stdin_io, stdout_io, stderr_io = ssh.exec_command(cmd_io, timeout=5)
                error_cpu = stderr_cpu.read().decode().strip()
                error_mem = stderr_mem.read().decode().strip()
                error_io = stderr_io.read().decode().strip()
                output_cpu = stdout_cpu.read().decode().strip()
                output_mem = stdout_mem.read().decode().strip()
                output_io = stdout_io.read().decode().strip()
                if error_cpu:
                    raise ValueError(f"Command {cmd_cpu} error: {error_cpu}")
                if error_mem:
                    raise ValueError(f"Command {cmd_mem} error: {error_mem}")
                if error_io:
                    raise ValueError(f"Command {cmd_io} error: {error_io}")
                if not output_cpu or not output_mem:
                    raise ValueError(f"未能获取进程ID {pid} 的性能数据")
                cpu_usage = float(output_cpu)
                memory_usage = float(output_mem)
                io_counters = {}
                for line in output_io.split('\n'):
                    parts = line.split(':')
                    if len(parts) == 2:
                        io_counters[parts[0].strip()] = int(parts[1].strip())
            else:
                # 获取所有进程的性能数据
                cmd_cpu = "top -b -n2 -d1 | grep 'Cpu(s)' | tail -n1"
                cmd_mem = "free -m | grep Mem"

                # 执行命令获取CPU和内存数据
                stdin_cpu, stdout_cpu, stderr_cpu = ssh.exec_command(cmd_cpu, timeout=5)
                stdin_mem, stdout_mem, stderr_mem = ssh.exec_command(cmd_mem, timeout=5)

                # 读取命令执行结果和错误信息
                error_cpu = stderr_cpu.read().decode().strip()
                error_mem = stderr_mem.read().decode().strip()
                output_cpu = stdout_cpu.read().decode().strip()
                output_mem = stdout_mem.read().decode().strip()

                # 检查命令执行错误
                if error_cpu:
                    raise ValueError(f"Command {cmd_cpu} error: {error_cpu}")
                if error_mem:
                    raise ValueError(f"Command {cmd_mem} error: {error_mem}")

                # 检查输出是否为空
                if not output_cpu or not output_mem:
                    raise ValueError("未能获取系统性能数据")

                # 解析CPU使用率（适配新格式）
                cpu_parts = output_cpu.split(',')  # 按逗号分割各项指标
                idle_value = None

                for part in cpu_parts:
                    part = part.strip()  # 去除空格
                    if part.endswith('id'):  # 查找包含空闲时间的项
                        # 提取数字部分（如 "95.8 id" 中的 "95.8"）
                        idle_value = part.split()[0]
                        break

                if idle_value is None:
                    raise ValueError(f"无法解析CPU空闲时间: {output_cpu}")

                # 计算CPU使用率
                cpu_usage = 100.0 - float(idle_value)

                # 解析内存使用率
                mem_parts = output_mem.split()
                if len(mem_parts) < 7:
                    raise ValueError("内存信息格式异常")

                # 计算内存使用率
                memory_usage = (float(mem_parts[2]) / float(mem_parts[1])) * 100 if float(mem_parts[1]) > 0 else 0

                # IO计数器（可根据需要补充实现）
                io_counters = {}
            performance_data = {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'io_counters': io_counters
            }
            return performance_data
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"获取远程性能数据失败: {str(e)}")
        finally:
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='sse')
