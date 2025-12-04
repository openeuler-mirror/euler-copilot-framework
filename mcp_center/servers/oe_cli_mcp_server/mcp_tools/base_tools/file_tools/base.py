import logging
import subprocess
import paramiko
from typing import Dict, Optional

from servers.oe_cli_mcp_server.config.base_config_loader import BaseConfig, LanguageEnum

# 初始化日志（保持原逻辑）
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_language() -> bool:
    """获取语言配置：True=中文，False=英文"""
    return BaseConfig().get_config().public_config.language == LanguageEnum.ZH

def get_remote_auth(ip: str) -> Optional[Dict]:
    """
    获取服务器认证信息：匹配IP/主机名对应的连接配置
    """
    for host_config in BaseConfig().get_config().public_config.remote_hosts:
        if ip in [host_config.host, host_config.name]:
            return {
                "host": host_config.host,
                "port": host_config.port,
                "username": host_config.username,
                "password": host_config.password
            }
    return None

def escape_shell_content(content: str) -> str:
    """
    转义shell命令中的特殊字符（避免注入和语法错误）
    """
    # 转义单引号（最关键，因为命令中用单引号包裹参数）
    return content.replace("'", "'\\''")

def init_result_dict(
        target_host: str,
        result_type: str = "list",  # result字段类型：list/str
        include_file_path: bool = False
) -> Dict:
    """
    初始化返回结果字典（统一结构）
    """
    result = {
        "success": False,
        "message": "",
        "result": [] if result_type == "list" else "",
        "target": target_host
    }
    if include_file_path:
        result["file_path"] = ""
    return result

def run_local_command(
        cmd: str,
        result: Dict,
        success_msg_zh: str,
        success_msg_en: str,
        is_list_result: bool = True,
        in_place: bool = False
) -> Dict:
    """
    执行本地命令并处理结果
    """
    try:
        logger.info(f"执行本地命令：{cmd}")
        output = subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.STDOUT
        )
        result["success"] = True
        result["message"] = success_msg_zh if get_language() else success_msg_en
        # 处理返回结果（in_place=True时不返回内容）
        if not in_place:
            if is_list_result:
                result["result"] = output.strip().split("\n") if output.strip() else []
            else:
                result["result"] = output.strip()
        # grep无匹配时退出码1，特殊处理
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and "grep" in cmd:
            result["success"] = True
            result["message"] = "未找到匹配内容" if get_language() else "No matching content found"
        else:
            result["message"] = f"本地执行失败：{e.output.strip()}" if get_language() else f"Local execution failed: {e.output.strip()}"
            logger.error(result["message"])
    except Exception as e:
        result["message"] = f"本地处理异常：{str(e)}" if get_language() else f"Local processing exception: {str(e)}"
        logger.error(result["message"])
    return result

def run_remote_command(
        cmd: str,
        remote_auth: Dict,
        result: Dict,
        success_msg_zh: str,
        success_msg_en: str,
        is_list_result: bool = True,
        in_place: bool = False
) -> Dict:
    """
    执行远程命令并处理结果（SSH连接封装）
    """
    ssh_conn: Optional[paramiko.SSHClient] = None
    try:
        # 初始化SSH客户端
        ssh_conn = paramiko.SSHClient()
        ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_conn.connect(
            hostname=remote_auth["host"],
            port=remote_auth["port"],
            username=remote_auth["username"],
            password=remote_auth["password"],
            timeout=10,
            banner_timeout=10
        )
        logger.info(f"已连接远程主机：{remote_auth['host']}，执行命令：{cmd}")

        # 执行命令
        stdin, stdout, stderr = ssh_conn.exec_command(cmd)
        stdout_msg = stdout.read().decode("utf-8", errors="replace").strip()
        stderr_msg = stderr.read().decode("utf-8", errors="replace").strip()

        # 处理结果
        if stderr_msg:
            result["message"] = f"远程执行失败：{stderr_msg}" if get_language() else f"Remote execution failed: {stderr_msg}"
            logger.error(result["message"])
        else:
            result["success"] = True
            result["message"] = success_msg_zh if get_language() else success_msg_en
            if not in_place:
                if is_list_result:
                    result["result"] = stdout_msg.split("\n") if stdout_msg else []
                else:
                    result["result"] = stdout_msg.strip()
    except paramiko.AuthenticationException:
        result["message"] = "SSH认证失败，请检查用户名和密码" if get_language() else "SSH authentication failed, check username and password"
        logger.error(result["message"])
    except TimeoutError:
        result["message"] = "SSH连接超时，请检查网络或主机状态" if get_language() else "SSH connection timed out, check network or host status"
        logger.error(result["message"])
    except Exception as e:
        result["message"] = f"远程处理异常：{str(e)}" if get_language() else f"Remote processing exception: {str(e)}"
        logger.error(result["message"])
    finally:
        # 关闭SSH连接
        if ssh_conn:
            transport = ssh_conn.get_transport()
            if transport and transport.is_active():
                ssh_conn.close()
                logger.info(f"已关闭与{remote_auth['host']}的SSH连接")
    return result