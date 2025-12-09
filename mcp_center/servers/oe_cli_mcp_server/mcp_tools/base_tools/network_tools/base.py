import logging
import subprocess
from typing import Dict, Optional, List

import paramiko

from config.public.base_config_loader import BaseConfig, LanguageEnum

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
                "password": host_config.password,
            }
    return None


def init_result(target_host: str) -> Dict:
    """初始化统一结果结构"""
    return {
        "success": False,
        "message": "",
        "result": [],
        "target": target_host,
    }


def _open_ssh(remote_auth: Dict) -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=remote_auth["host"],
        port=remote_auth["port"],
        username=remote_auth["username"],
        password=remote_auth["password"],
        timeout=10,
        banner_timeout=10,
    )
    return ssh


def _build_fix_command() -> str:
    """
    构造修复 ifcfg-ens3 中 BOOTPROTO 并重启 NetworkManager 的命令
    仅做问题描述中的三件事：
    1. 校验文件存在
    2. 设置 BOOTPROTO=dhcp
    3. systemctl restart NetworkManager
    """
    ifcfg_path = "/etc/sysconfig/network-scripts/ifcfg-ens3"
    parts: List[str] = []
    # 确认配置文件存在
    parts.append(
        f"IFCFG='{ifcfg_path}'; "
        "if [ ! -f \"$IFCFG\" ]; then "
        "echo 'ifcfg-ens3 not found'; "
        "exit 1; "
        "fi"
    )
    # 规范化 BOOTPROTO 行：若存在则直接替换为 dhcp
    parts.append(
        "sed -i -e 's/^[#]*[[:space:]]*BOOTPROTO=.*/BOOTPROTO=dhcp/' \"$IFCFG\""
    )
    # 若不存在 BOOTPROTO 行，则追加一行
    parts.append(
        "grep -q '^[[:space:]]*BOOTPROTO=' \"$IFCFG\" || echo 'BOOTPROTO=dhcp' >> \"$IFCFG\""
    )
    # 重启 NetworkManager 服务
    parts.append("systemctl restart NetworkManager")
    return " && ".join(parts)


def fix_network_bootproto_issue(target: Optional[str] = None) -> Dict:
    """
    修复 NetworkManager 未自动获取 IP 的问题：
    - 编辑 /etc/sysconfig/network-scripts/ifcfg-ens3，将 BOOTPROTO 修正为 dhcp
    - 重启 NetworkManager 服务
    """
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    is_zh = get_language()
    result = init_result(target_host)
    steps: List[str] = []

    fix_cmd = _build_fix_command()

    # 本地修复逻辑
    if target_host == "127.0.0.1":
        try:
            steps.append(
                "开始修复本机 ifcfg-ens3 配置并重启 NetworkManager"
                if is_zh
                else "Start fixing local ifcfg-ens3 and restart NetworkManager"
            )
            completed = subprocess.run(
                fix_cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout = completed.stdout.strip()
            stderr = completed.stderr.strip()
            if stdout:
                steps.extend(stdout.splitlines())
            if stderr:
                steps.extend(stderr.splitlines())

            result["success"] = True
            result["message"] = (
                "网络配置已修复：BOOTPROTO=dhcp，NetworkManager 已重启"
                if is_zh
                else "Network configuration fixed: BOOTPROTO=dhcp and NetworkManager restarted"
            )
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() if e.stderr else str(e)
            result["message"] = (
                f"修复网络配置失败：{err}"
                if is_zh
                else f"Failed to fix network configuration: {err}"
            )
            steps.append(result["message"])

        result["result"] = steps
        return result

    # 远程修复逻辑（与本地相同操作，通过 SSH 执行）
    remote_auth = get_remote_auth(target_host)
    if not remote_auth or not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = (
            f"未找到远程主机（{target_host}）的认证配置"
            if is_zh
            else f"Authentication config for remote host ({target_host}) not found"
        )
        result["result"] = [result["message"]]
        return result

    ssh: Optional[paramiko.SSHClient] = None
    try:
        ssh = _open_ssh(remote_auth)
        steps.append(
            f"开始修复远程主机（{target_host}）的 ifcfg-ens3 配置并重启 NetworkManager"
            if is_zh
            else f"Start fixing remote host ({target_host}) ifcfg-ens3 and restart NetworkManager"
        )
        stdin, stdout, stderr = ssh.exec_command(fix_cmd)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()

        if out:
            steps.extend(out.splitlines())
        if err:
            steps.extend(err.splitlines())

        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            result["success"] = True
            result["message"] = (
                f"远程主机（{target_host}）网络配置已修复：BOOTPROTO=dhcp，NetworkManager 已重启"
                if is_zh
                else f"Remote host ({target_host}) network configuration fixed: BOOTPROTO=dhcp and NetworkManager restarted"
            )
        else:
            result["message"] = (
                f"远程修复网络配置失败：{err}"
                if is_zh
                else f"Failed to fix remote network configuration: {err}"
            )
            steps.append(result["message"])
    except paramiko.AuthenticationException:
        result["message"] = (
            "SSH 认证失败，请检查用户名和密码"
            if is_zh
            else "SSH authentication failed, check username and password"
        )
        steps.append(result["message"])
    except Exception as e:
        result["message"] = (
            f"远程修复网络配置异常：{str(e)}"
            if is_zh
            else f"Remote network fix exception: {str(e)}"
        )
        steps.append(result["message"])
    finally:
        if ssh:
            ssh.close()

    result["result"] = steps
    return result



