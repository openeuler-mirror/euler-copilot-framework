from typing import Union
import paramiko
import subprocess
from mcp.server import FastMCP
from config.public.base_config_loader import LanguageEnum
from config.private.chown.config_loader import ChownConfig
mcp = FastMCP("Chown MCP Server", host="0.0.0.0", port=ChownConfig().get_config().private_config.port)


@mcp.tool(
    name="chown_change_owner_tool"
    if ChownConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    "chown_change_owner_tool",
    description='''
    使用chown命令设置文件所有者和文件关联组
    1. 输入值如下：
        - host: 远程主机名称或IP地址，若不提供则表示对本机文件进行修改
        - owner_group: 文件所有者和文件关联组
        - file: 要修改目标文件的路径
    2. 返回值为布尔值，表示文件所有者和文件关联组是否修改成功
    '''
    if ChownConfig().get_config().public_config.language == LanguageEnum.ZH
    else
    '''
    Use the `chown` command to set the file owner and associated group of a file.
    1. Input values are as follows:
        - host: The name or IP address of the remote host. If not provided, it indicates that the file on the local machine is to be modified.
        - owner_group: File owner and associated group of the file
        - file: The path of the target file to be modified
    2. The return value is a boolean value, indicating whether the file owner and associated group were modified successfully
    '''
)
def chown_change_owner_tool(host: Union[str, None] = None, owner_group: str = None, file: str = None) -> bool:
    """使用chown命令设置文件所有者和文件关联组"""
    if host is None:
        if not owner_group or not file :
            if ChownConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise ValueError("chown要修改的目标文件及文件所有者不能为空")
            else:
                raise ValueError("The target file and file owner for chown cannot be empty")
        try:
            command = ['chown']
            command.append(owner_group)
            command.append(file)
            result = subprocess.run(command, capture_output=True, text=True)
            returncode = result.returncode
            if returncode == 0:
                return True
            else:
                return False
        except Exception as e:
            if ChownConfig().get_config().public_config.language == LanguageEnum.ZH:
                raise RuntimeError(f"执行 {command} 命令时发生未知错误: {str(e)}") from e
            else:
                raise RuntimeError(f"An unknown error occurred while obtaining memory information: {str(e)}") from e
    else:
        for host_config in ChownConfig().get_config().public_config.remote_hosts:
            if host == host_config.name or host == host_config.host:
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
                    if not owner_group or not file :
                        if ChownConfig().get_config().public_config.language == LanguageEnum.ZH:
                            raise ValueError("chown要修改的目标文件及文件所有者不能为空")
                        else:
                            raise ValueError("The target file and file owner for chown cannot be empty")
                    command = f'chown {owner_group} {file}'
                    stdin, stdout, stderr = ssh.exec_command(command, timeout=20)
                    error = stderr.read().decode().strip()
                    
                    if error:
                        if ChownConfig().get_config().public_config.language == LanguageEnum.ZH:
                            raise ValueError(f"执行 {command} 命令失败: {error}")
                        else:
                            raise ValueError(f"Command {command} execution failed: {error}")
                    else:
                        return True
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
        if ChownConfig().get_config().public_config.language == LanguageEnum.ZH:
            raise ValueError(f"未找到远程主机: {host}")
        else:
            raise ValueError(f"Remote host not found: {host}")


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='sse')
