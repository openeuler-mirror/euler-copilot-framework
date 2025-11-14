from typing import Union
import paramiko
import subprocess
import os
from mcp.server import FastMCP
from config.public.base_config_loader import LanguageEnum
from config.private.cat.config_loader import CatConfig
mcp = FastMCP("Cat MCP Server", host="0.0.0.0", port=CatConfig().get_config().private_config.port)


@mcp.tool(
    name="cat_file_view_tool"
    if CatConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    "cat_file_view_tool",
    description='''
    使用cat命令查看文件内容
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示查看本机指定文件内容
        - file: 要查看文件的路径
    2. 返回值为字符串，为返回的文件内容
    '''
    if CatConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Use the cat command to view file contents
    1. Input values are as follows:
        - host: The name or IP address of the remote host; if not provided, it indicates viewing the contents of a specified file on the local machine
        - file: The path of the file to be viewed
    2. The return value is a string, which is the content of the returned file
    '''

)
def cat_file_view_tool(host: Union[str, None] = None, file: str = None) -> str:
    """使用cat命令查看文件内容"""
    if host is None:
        if not file:
            raise ValueError("文件路径不能为空" if CatConfig().get_config().public_config.language == LanguageEnum.ZH 
                                else "File path cannot be empty")
        try:
            if not os.path.exists(file):
                raise FileNotFoundError(f"文件不存在: {file}" if CatConfig().get_config().public_config.language == LanguageEnum.ZH 
                                        else f"File not found: {file}")
            command = ['cat', f'{file}']
            result = subprocess.run(command, capture_output=True, text=True)
            lines = result.stdout
            return lines
        except Exception as e:
            if CatConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise RuntimeError(f"获取 {command} 输出信息时发生未知错误: {str(e)}") from e
            else:
                raise RuntimeError(f"An unknown error occurred while retrieving the output information for {command} : {str(e)}") from e
    else:
        for host_config in CatConfig().get_config().public_config.remote_hosts:
            if host == host_config.name or host == host_config.host:
                if not file:
                    raise ValueError("文件路径不能为空" if CatConfig().get_config().public_config.language == LanguageEnum.ZH 
                                    else "File path cannot be empty")
                try:
                    # 建立SSH连接
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        hostname=host_config.host,
                        port=host_config.port,
                        username=host_config.username,
                        password=host_config.password
                    )
                    if not os.path.exists(file):
                        raise FileNotFoundError(f"文件不存在: {file}" if CatConfig().get_config().public_config.language == LanguageEnum.ZH 
                                                else f"File not found: {file}")
                    command = f'cat {file}'
                    stdin, stdout, stderr = ssh.exec_command(command, timeout=10)
                    error = stderr.read().decode().strip()
                    result = stdout.read().decode().strip()
                    if error:
                        if CatConfig().get_config().public_config.language == LanguageEnum.ZH:
                            raise ValueError(f"执行命令 {command} 错误：{error}")
                        else:
                            raise ValueError(f"Error executing command {command}: {error}")
                    return result
                except paramiko.AuthenticationException:
                    raise ValueError("SSH认证失败，请检查用户名和密码")
                except paramiko.SSHException as e:
                    raise ValueError(f"SSH连接错误: {str(e)}")
                except Exception as e:
                    raise ValueError(f"远程执行 {command} 失败: {str(e)}")
                finally:
                    # 确保SSH连接关闭
                    if ssh is not None:
                        try:
                            ssh.close()
                        except Exception:
                            pass
        if CatConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError(f"未找到远程主机: {host}")
        else:
            raise ValueError(f"Remote host not found: {host}")


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='sse')
