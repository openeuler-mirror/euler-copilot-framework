import logging
import socket
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


def ssh_port_ping(target: str, port: int = 22, timeout: int = 5) -> Dict:
    """通过 TCP 连接检测 SSH 端口连通性"""
    result = init_result(target)
    is_zh = get_language()
    try:
        with socket.create_connection((target, port), timeout=timeout):
            result["success"] = True
            result["message"] = (
                f"SSH 端口 {port} 可达" if is_zh else f"SSH port {port} is reachable"
            )
    except Exception as e:
        result["message"] = (
            f"SSH 端口 {port} 不可达：{str(e)}"
            if is_zh
            else f"SSH port {port} is unreachable: {str(e)}"
        )
    result["result"] = [result["message"]]
    return result


def _run_local(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


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


def check_sshd_status(target: Optional[str]) -> Dict:
    """执行 systemctl status sshd"""
    target_host = target.strip() if target else "127.0.0.1"
    result = init_result(target_host)
    is_zh = get_language()

    cmd = ["/usr/bin/systemctl ", "status", "sshd"]

    # 本地
    if target_host == "127.0.0.1":
        try:
            cp = _run_local(cmd)
            result["success"] = True
            result["message"] = (
                "本地 sshd 状态获取成功" if is_zh else "Local sshd status fetched"
            )
            result["result"] = cp.stdout.strip().splitlines()
        except subprocess.CalledProcessError as e:
            result["message"] = (
                f"本地 sshd 状态获取失败：{e.stderr.strip()}"
                if is_zh
                else f"Failed to get local sshd status: {e.stderr.strip()}"
            )
        return result

    # 远程
    remote_auth = get_remote_auth(target_host)
    if not remote_auth or not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = (
            "远程认证配置缺失" if is_zh else "Remote auth config missing"
        )
        return result

    ssh: Optional[paramiko.SSHClient] = None
    try:
        ssh = _open_ssh(remote_auth)
        stdin, stdout, stderr = ssh.exec_command("/usr/bin/systemctl  status sshd")
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if err and "Active:" not in out:
            result["message"] = (
                f"远程 sshd 状态获取失败：{err}"
                if is_zh
                else f"Failed to get remote sshd status: {err}"
            )
        else:
            result["success"] = True
            result["message"] = (
                "远程 sshd 状态获取成功" if is_zh else "Remote sshd status fetched"
            )
            result["result"] = out.splitlines()
    except paramiko.AuthenticationException:
        result["message"] = (
            "SSH 认证失败，请检查用户名和密码"
            if is_zh
            else "SSH authentication failed, check username and password"
        )
    except Exception as e:
        result["message"] = (
            f"远程 sshd 状态检查异常：{str(e)}"
            if is_zh
            else f"Remote sshd status check exception: {str(e)}"
        )
    finally:
        if ssh:
            ssh.close()
    return result


def fix_sshd_config_and_restart(target: Optional[str]) -> Dict:
    """
    修复 /etc/ssh/sshd_config 中的 Port/PermitRootLogin/PasswordAuthentication
    并执行 systemctl restart sshd
    """
    target_host = target.strip() if target else "127.0.0.1"
    result = init_result(target_host)
    is_zh = get_language()

    # 需要确保的配置行
    desired_lines = {
        "Port": "Port 22",
        "PermitRootLogin": "PermitRootLogin yes",
        "PasswordAuthentication": "PasswordAuthentication yes",
    }

    def build_sed_commands() -> str:
        """
        为远程一次性执行构造 sed & restart 命令：
        - 先针对每个键进行替换/解注释
        - 若不存在目标键则追加
        - 最后重启 sshd
        """
        sed_parts = []
        # 替换或解注释三项配置
        sed_parts.append(
            r"sed -i -e 's/^[#]*[[:space:]]*Port[[:space:]].*/Port 22/' "
            r"-e 's/^[#]*[[:space:]]*PermitRootLogin[[:space:]].*/PermitRootLogin yes/' "
            r"-e 's/^[#]*[[:space:]]*PasswordAuthentication[[:space:]].*/PasswordAuthentication yes/' "
            r"/etc/ssh/sshd_config"
        )
        # 若 key 不存在则追加
        for k, line in desired_lines.items():
            sed_parts.append(
                f"grep -q '^{k}[[:space:]]' /etc/ssh/sshd_config || "
                f"echo '{line}' >> /etc/ssh/sshd_config"
            )
        # 重启 sshd
        sed_parts.append("/usr/bin/systemctl  restart sshd")
        # 组合为单条 shell 命令
        return " && ".join(sed_parts)

    # 本地修复
    if target_host == "127.0.0.1":
        messages: List[str] = []
        try:
            # 直接执行与远程相同的 shell 逻辑
            shell_cmd = build_sed_commands()
            cp = subprocess.run(
                shell_cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if cp.stdout.strip():
                messages.extend(cp.stdout.strip().splitlines())
            if cp.stderr.strip():
                messages.extend(cp.stderr.strip().splitlines())
            result["success"] = True
            result["message"] = (
                "本地 sshd 配置已修复并重启"
                if is_zh
                else "Local sshd config fixed and service restarted"
            )
            if not messages:
                messages.append(result["message"])
            result["result"] = messages
        except subprocess.CalledProcessError as e:
            result["message"] = (
                f"本地 sshd 修复失败：{e.stderr.strip()}"
                if is_zh
                else f"Failed to fix local sshd: {e.stderr.strip()}"
            )
            result["result"] = [result["message"]]
        return result

    # 远程修复
    remote_auth = get_remote_auth(target_host)
    if not remote_auth or not (remote_auth["username"] and remote_auth["password"]):
        result["message"] = (
            "远程认证配置缺失" if is_zh else "Remote auth missing"
        )
        return result

    ssh: Optional[paramiko.SSHClient] = None
    try:
        ssh = _open_ssh(remote_auth)
        shell_cmd = build_sed_commands()
        stdin, stdout, stderr = ssh.exec_command(shell_cmd)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()

        messages: List[str] = []
        if out:
            messages.extend(out.splitlines())
        if err:
            messages.extend(err.splitlines())

        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            result["success"] = True
            result["message"] = (
                "远程 sshd 配置已修复并重启"
                if is_zh
                else "Remote sshd config fixed and service restarted"
            )
        else:
            result["message"] = (
                f"远程 sshd 修复失败：{err}"
                if is_zh
                else f"Failed to fix remote sshd: {err}"
            )
        if not messages:
            messages.append(result["message"])
        result["result"] = messages
    except paramiko.AuthenticationException:
        result["message"] = (
            "SSH 认证失败，请检查用户名和密码"
            if is_zh
            else "SSH authentication failed, check username and password"
        )
        result["result"] = [result["message"]]
    except Exception as e:
        result["message"] = (
            f"远程 sshd 修复异常：{str(e)}"
            if is_zh
            else f"Remote sshd fix exception: {str(e)}"
        )
        result["result"] = [result["message"]]
    finally:
        if ssh:
            ssh.close()

    return result


def fix_sshd_issue(target: Optional[str], port: int = 22) -> Dict:
    """
    整体解决 SSH 连接失败问题的工具，按顺序执行：
    1. 检查 SSH 端口连通性（ping 端口）
    2. 检查 sshd 服务状态（systemctl status sshd）
    3. 修复 sshd_config 关键配置并重启 sshd
    """
    target_host = target.strip() if (target and isinstance(target, str)) else "127.0.0.1"
    is_zh = get_language()
    result = init_result(target_host)

    steps: List[str] = []

    # 步骤 1：端口连通性检查
    steps.append(
        "=== 步骤1: 检查 SSH 端口连通性 ==="
        if is_zh
        else "=== Step 1: Check SSH port connectivity ==="
    )
    ping_res = ssh_port_ping(target_host, port=port)
    steps.extend(ping_res.get("result", []) or [ping_res.get("message", "")])

    # 步骤 2：sshd 状态检查
    steps.append(
        "=== 步骤2: 检查 sshd 服务状态 ==="
        if is_zh
        else "=== Step 2: Check sshd service status ==="
    )
    status_res = check_sshd_status(target_host)
    if status_res.get("message"):
        steps.append(status_res["message"])
    # 只展示前几行关键信息，避免输出过长
    status_lines = status_res.get("result") or []
    if status_lines:
        steps.extend(status_lines[:5])

    # 步骤 3：修复配置并重启 sshd
    steps.append(
        "=== 步骤3: 修复 sshd 配置并重启服务 ==="
        if is_zh
        else "=== Step 3: Fix sshd config and restart service ==="
    )
    fix_res = fix_sshd_config_and_restart(target_host)
    if fix_res.get("message"):
        steps.append(fix_res["message"])
    fix_lines = fix_res.get("result") or []
    if fix_lines:
        steps.extend(fix_lines)

    # 综合结果：以修复步骤结果为准
    result["success"] = bool(fix_res.get("success"))
    result["message"] = (
        "SSH 问题处理完成" if is_zh else "SSH issue handling finished"
    )
    if not result["success"] and fix_res.get("message"):
        # 若修复失败，附加更明确的错误说明
        result["message"] = fix_res["message"]

    result["result"] = steps
    return result



