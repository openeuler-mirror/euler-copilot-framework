from typing import Union, List, Dict, Any
import paramiko
import subprocess
import re
from mcp.server import FastMCP
from config.public.base_config_loader import LanguageEnum
from config.private.disk_manager.config_loader import DiskManagerConfig
mcp = FastMCP("Remote info MCP Server", host="0.0.0.0", port=DiskManagerConfig().get_config().private_config.port)


@mcp.tool(
    name="get_disk_status_tool"
    if DiskManagerConfig().get_config().public_config.language == LanguageEnum.EN
    else "get_disk_status_tool",
    description='''
    使用iostat命令获取磁盘使用情况
    输入值如下:
        - host: 远程主机名或IP地址, 不传表示获取本机磁盘使用情况
        - time_gap: 采样间隔, 默认为0.1秒
        - count: 采样次数, 默认为1次
    输出值如下:
        - device: 设备名
        - tps: 每秒传输次数
        - kB_read/s: 每秒读取的千字节数
        - kB_wrtn/s: 每秒写入的千字节数
        - KB_dscd/s: 每秒丢弃的千字节数
        - kB_read: 读取的千字节总数
        - kB_wrtn: 写入的千字节总数
        - KB_dscd: 丢弃的千字节总数
    ''' if DiskManagerConfig().get_config().public_config.language == LanguageEnum.EN
    else '''
    Use the iostat command to get disk usage
    Input values are as follows:
        - host: Remote hostname or IP address, not passed to get local disk usage
        - time_gap: Sampling interval, default is 0.1 seconds
        - count: Number of samples, default is 1 time
    Output values are as follows:
        - device: Device name
        - tps: Transfers per second
        - kB_read/s: Kilobytes read per second
        - kB_wrtn/s: Kilobytes written per second
        - KB_dscd/s: Kilobytes discarded per second
        - kB_read: Total kilobytes read
        - kB_wrtn: Total kilobytes written
        - KB_dscd: Total kilobytes discarded
    ''',

)
async def get_disk_status(host: Union[str, None] = None,
                          time_gap: int = 1,
                          count: int = 1) -> List[Dict[str, Any]]:
    """使用iostat命令获取磁盘使用情况"""
    if time_gap <= 0 or count <= 0:
        raise ValueError("time_gap和count必须为正数")
    if host is None:
        # 获取本机磁盘使用情况
        try:
            result = subprocess.run(['iostat', '-d', str(time_gap), str(count)],
                                    capture_output=True, text=True, check=True)
            output = result.stdout
            lines = output.strip().split('\n')
            disk_info_dict = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        disk_info = {
                            'device': parts[0],
                            'tps': float(parts[1]),
                            'kB_read/s': float(parts[2]),
                            'kB_wrtn/s': float(parts[3]),
                            'KB_dscd/s': float(parts[4]),
                            'kB_read': int(parts[5]),
                            'kB_wrtn': int(parts[6]),
                            'KB_dscd': int(parts[7])
                        }
                        if parts[0] not in disk_info_dict:
                            disk_info_dict[parts[0]] = []
                        disk_info_dict[parts[0]].append(disk_info)
                    except ValueError:
                        continue
            # 计算平均值
            disk_info = []
            for device, infos in disk_info_dict.items():
                avg_info = {
                    'device': device,
                    'tps': sum(info['tps'] for info in infos) / len(infos),
                    'kB_read/s': sum(info['kB_read/s'] for info in infos) / len(infos),
                    'kB_wrtn/s': sum(info['kB_wrtn/s'] for info in infos) / len(infos),
                    'KB_dscd/s': sum(info['KB_dscd/s'] for info in infos) / len(infos),
                    'kB_read': sum(info['kB_read'] for info in infos),
                    'kB_wrtn': sum(info['kB_wrtn'] for info in infos),
                    'KB_dscd': sum(info['KB_dscd'] for info in infos)
                }
                disk_info.append(avg_info)
            return disk_info
        except Exception as e:
            return [{"error": str(e)}]
    else:
        # 获取远程主机磁盘使用情况
        try:
            for host_config in DiskManagerConfig().get_config().public_config.remote_hosts:
                if host == host_config.name or host == host_config.host:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        hostname=host_config.host,
                        port=host_config.port,
                        username=host_config.username,
                        password=host_config.password
                    )
                    stdin, stdout, stderr = ssh.exec_command('iostat -d {} {}'.format(time_gap, count))
                    output = stdout.read().decode()
                    error = stderr.read().decode()
                    if error:
                        raise ValueError(f"远程命令执行错误: {error}")
                    lines = output.strip().split('\n')
                    disk_info_dict = {}
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 8:
                            try:
                                disk_info = {
                                    'device': parts[0],
                                    'tps': float(parts[1]),
                                    'kB_read/s': float(parts[2]),
                                    'kB_wrtn/s': float(parts[3]),
                                    'KB_dscd/s': float(parts[4]),
                                    'kB_read': int(parts[5]),
                                    'kB_wrtn': int(parts[6]),
                                    'KB_dscd': int(parts[7])
                                }
                                if parts[0] not in disk_info_dict:
                                    disk_info_dict[parts[0]] = []
                                disk_info_dict[parts[0]].append(disk_info)
                            except ValueError:
                                continue
                    # 计算平均值
                    disk_info = []
                    for device, infos in disk_info_dict.items():
                        avg_info = {
                            'device': device,
                            'tps': sum(info['tps'] for info in infos) / len(infos),
                            'kB_read/s': sum(info['kB_read/s'] for info in infos) / len(infos),
                            'kB_wrtn/s': sum(info['kB_wrtn/s'] for info in infos) / len(infos),
                            'KB_dscd/s': sum(info['KB_dscd/s'] for info in infos) / len(infos),
                            'kB_read': sum(info['kB_read'] for info in infos),
                            'kB_wrtn': sum(info['kB_wrtn'] for info in infos),
                            'KB_dscd': sum(info['KB_dscd'] for info in infos)
                        }
                        disk_info.append(avg_info)
                    return disk_info
            if DiskManagerConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机: {host}")
            else:
                raise ValueError(f"Remote host not found: {host}")
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
    name="disk_io_insight_tool"
    if DiskManagerConfig().get_config().public_config.language == LanguageEnum.EN
    else "disk_io_insight_tool",
    description='''
    使用iotop命令获取磁盘IO使用情况
    输入值如下:
        - host: 远程主机名或IP地址, 不传表示获取本机磁盘IO使用情况
        - time_gap: 采样间隔, 默认为1秒
        - count: 采样次数, 默认为1次
    输出值如下:
        - pid: 进程ID
        - user: 进程所属用户
        - disk_read: 磁盘读取速率
        - disk_write: 磁盘写入速率
        - swapin: 交换区使用率
        - io: IO使用率
        - command: 进程命令
    ''' if DiskManagerConfig().get_config().public_config.language == LanguageEnum.EN
    else '''
    Use the iotop command to get disk IO usage
    Input values are as follows:
        - host: Remote hostname or IP address, not passed to get local disk IO usage
        - time_gap: Sampling interval, default is 1 second
        - count: Number of samples, default is 1 time
    Output values are as follows:
        - pid: Process ID
        - user: Process owner
        - disk_read: Disk read rate
        - disk_write: Disk write rate
        - swapin: Swap usage
        - io: IO usage
        - command: Process command
    '''
)
def disk_io_insight(host: Union[str, None] = None,
                    time_gap: int = 1,
                    count: int = 1) -> List[Dict[str, Any]]:
    """使用iotop命令获取磁盘IO使用情况"""
    if time_gap <= 0 or count <= 0:
        raise ValueError("time_gap和count必须为正数")
    if host is None:
        # 获取本机磁盘IO使用情况
        try:
            result = subprocess.run(
                ['iotop', '-b', '-n', str(count), '-d', str(time_gap)],
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout
            lines = output.strip().split('\n')
        except Exception as e:
            return [{"error": str(e)}]
    else:
        # 获取远程主机磁盘IO使用情况
        try:
            lines = None
            for host_config in DiskManagerConfig().get_config().public_config.remote_hosts:
                if host == host_config.name or host == host_config.host:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        hostname=host_config.host,
                        port=host_config.port,
                        username=host_config.username,
                        password=host_config.password
                    )
                    stdin, stdout, stderr = ssh.exec_command('iotop -b -n {} -d {}'.format(count, time_gap))
                    output = stdout.read().decode()
                    error = stderr.read().decode()
                    if error:
                        raise ValueError(f"远程命令执行错误: {error}")
                    lines = output.strip().split('\n')
            if lines is None:
                if DiskManagerConfig().get_config().public_config.language == LanguageEnum.ZH:
                    raise ValueError(f"未找到远程主机: {host}")
                else:
                    raise ValueError(f"Remote host not found: {host}")
        except paramiko.AuthenticationException:
            raise ValueError("SSH认证失败，请检查用户名和密码")
        except paramiko.SSHException as e:
            raise ValueError(f"SSH连接错误: {str(e)}")
    try:
        io_info = []
        # 处理PID、优先级、用户、磁盘读写速率（含单位）、swapin、IO、命令
        pattern = r'^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\d+\.\d+)\s+(\S+)\s+(\d+\.\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*?)\s*$'

        # 跳过标题行（通常是前3行）
        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = re.match(pattern, line)
            if match:
                try:
                    io_data = {
                        'pid': int(match.group(1)),
                        'priority': match.group(2),  # 如be/4
                        'user': match.group(3),
                        'disk_read': f"{match.group(4)} {match.group(5)}",  # 组合数值和单位
                        'disk_write': f"{match.group(6)} {match.group(7)}",  # 组合数值和单位
                        'swapin': match.group(8),
                        'io': match.group(9),
                        'command': match.group(10)
                    }
                    io_info.append(io_data)
                except ValueError:
                    continue
        return io_info
    except Exception as e:
        return [{"error": str(e)}]


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='sse')
