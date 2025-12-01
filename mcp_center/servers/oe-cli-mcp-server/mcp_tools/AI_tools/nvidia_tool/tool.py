from typing import Any, Dict, Optional, Union
import paramiko
from config.base_config_loader import BaseConfig, LanguageEnum

from mcp_tools.AI_tools.nvidia_tool.base import _format_gpu_info, _get_local_gpu_status, _get_remote_gpu_status_via_ssh


async def nvidia_smi_status(
        host: Union[str, None] = None,
        gpu_index: Optional[int] = None,
        include_processes: bool = False,
        lang: Optional[LanguageEnum] = LanguageEnum.ZH,
        config: Optional[Any] = None
    ) -> Dict[str, Any]:
        """获取GPU状态信息"""
        result = {
            "success": False,
            "message": "",
            "data": {}
        }

        # 1. 本地查询分支（host为空）
        if host is None:
            try:
                raw_info = _get_local_gpu_status(gpu_index, include_processes, lang)
                formatted_data = _format_gpu_info(raw_info, "localhost", include_processes, lang)

                result["success"] = True
                result["message"] = "成功获取本地主机的GPU状态信息" if lang == LanguageEnum.ZH else "Successfully obtained GPU status information for the local host"
                result["data"] = formatted_data
                return result
            except Exception as e:
                error_msg = f"获取本地GPU状态信息失败: {str(e)}" if lang == LanguageEnum.ZH else f"Failed to obtain local GPU status information: {str(e)}"
                result["message"] = error_msg
                return result

        # 2. 远程查询分支（host不为空）
        else:
            for host_config in BaseConfig().get_config().public_config.remote_hosts:
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

                        # 远程查询GPU状态
                        raw_info = _get_remote_gpu_status_via_ssh(ssh, gpu_index, include_processes, lang)
                        ssh.close()

                        # 格式化结果
                        formatted_data = _format_gpu_info(raw_info, host_config.host, include_processes, lang)
                        result["success"] = True
                        result["message"] = f"成功获取远程主机 {host_config.host} 的GPU状态信息" if lang == LanguageEnum.ZH else f"Successfully obtained GPU status information for remote host {host_config.host}"
                        result["data"] = formatted_data
                        return result

                    except paramiko.AuthenticationException:
                        # 认证失败（双语提示）
                        if 'ssh' in locals():
                            ssh.close()
                        err_msg = "SSH认证失败，请检查用户名和密码" if lang == LanguageEnum.ZH else "SSH authentication failed, please check username and password"
                        result["message"] = err_msg
                        return result
                    except Exception as e:
                        # 其他远程执行异常（双语提示）
                        if 'ssh' in locals():
                            ssh.close()
                        err_msg = f"远程主机 {host_config.host} 查询异常: {str(e)}" if lang == LanguageEnum.ZH else f"Remote host {host_config.host} query error: {str(e)}"
                        result["message"] = err_msg
                        return result

            # 未匹配到远程主机（双语异常）
            if lang == LanguageEnum.ZH:
                raise ValueError(f"未找到远程主机配置: {host}")
            else:
                raise ValueError(f"Remote host configuration not found: {host}")