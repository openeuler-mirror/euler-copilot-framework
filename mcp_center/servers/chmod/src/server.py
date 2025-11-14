from typing import Union
import paramiko
import subprocess
from mcp.server import FastMCP
from config.public.base_config_loader import LanguageEnum
from config.private.chmod.config_loader import ChmodConfig

mcp = FastMCP("Chmod MCP Server", host="0.0.0.0", port=ChmodConfig().get_config().private_config.port)

@mcp.tool(
    name="chmod_change_mode_tool"
    if ChmodConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    "chmod_change_mode_tool",
    description='''
    使用chmod命令设置文件或目录权限
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示对本机文件进行操作
        - mode: 权限模式（如755、644等）
        - file: 要修改的目标文件或目录
    2. 返回值为布尔值，表示权限是否修改成功
    '''
    if ChmodConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Use the `chmod` command to set the permission of a file or directory.
    1. Input values are as follows:
        - host: Remote host name or IP address, if not provided, it means to modify the file on the local machine
        - mode: Permission mode (such as 755, 644, etc.)
        - file: Target file or directory to modify
    2. Return value is a boolean value indicating whether the permission is modified successfully
    '''
)
def chmod_change_mode_tool(host: Union[str, None] = None, mode: str = None, file: str = None) -> bool:
    """使用chmod命令设置文件或目录权限"""
    if host is None:
        if not mode or not file:
            if ChmodConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError("chmod要修改的目标文件及权限模式不能为空")
            else:
                raise ValueError("The target file and permission mode for chmod cannot be empty")
        try:
            command = ['chmod', mode, file]
            result = subprocess.run(command, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            if ChmodConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise RuntimeError(f"执行 {command} 命令时发生未知错误: {str(e)}") from e
            else:
                raise RuntimeError(f"An unknown error occurred while executing the {command} command: {str(e)}") from e
    else:
        for host_config in ChmodConfig().get_config().public_config.remote_hosts:
            if host == host_config.name or host == host_config.host:
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        hostname=host_config.host,
                        port=host_config.port,
                        username=host_config.username,
                        password=host_config.password
                    )
                    if not mode or not file:
                        if ChmodConfig().get_config().public_config.language == LanguageEnum.ZH:
                            raise ValueError("chmod要修改的目标文件及权限模式不能为空")
                        else:
                            raise ValueError("The target file and permission mode for chmod cannot be empty")
                    command = f'chmod {mode} {file}'
                    stdin, stdout, stderr = ssh.exec_command(command, timeout=20)
                    error = stderr.read().decode().strip()
                    return not error
                except Exception as e:
                    raise ValueError(f"远程执行 {command} 失败: {str(e)}")
                finally:
                    if ssh is not None:
                        try:
                            ssh.close()
                        except Exception:
                            pass
        raise ValueError(f"未找到远程主机: {host}")

if __name__ == "__main__":
    mcp.run(transport='sse')