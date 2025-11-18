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


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='sse')
