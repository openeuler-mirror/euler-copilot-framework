from typing import Dict, Any, Optional
import subprocess
import tempfile
import re
import paramiko
from mcp.server import FastMCP
from config.public.base_config_loader import LanguageEnum
from config.private.cache_miss_audit.config_loader import CacheMissAuditConfig

mcp = FastMCP(
    "Cache Miss Audit Tool MCP Server",
    host="0.0.0.0",
    port=CacheMissAuditConfig().get_config().private_config.port
)

@mcp.tool(
    name="cache_miss_audit_tool"
    if CacheMissAuditConfig().get_config().public_config.language == LanguageEnum.ZH
    else "cache_miss_audit_tool",
    description="""
    通过 `perf stat -a -e cache-misses,cycles,instructions sleep 10` 采集整机的微架构指标。
    参数：
        host : 可选，远程主机 IP/域名；留空则采集本机。
    返回：
        dict  {
            "cache_misses": int,
            "cycles"      : int,
            "instructions": int,
            "ipc"         : float,
            "seconds"     : float
        }
    """
    if CacheMissAuditConfig().get_config().public_config.language == LanguageEnum.ZH
    else """
    Collect whole-system micro-arch metrics via
    `perf stat -a -e cache-misses,cycles,instructions sleep 10`.
    Args:
        host : Optional remote IP/hostname; analyse local if omitted.
    Returns:
        dict  {
            "cache_misses": int,
            "cycles"      : int,
            "instructions": int,
            "ipc"         : float,
            "seconds"     : float
        }
    """
)
def cache_miss_audit_tool(host: Optional[str] = None) -> Dict[str, Any]:
    """采集并解析 perf stat 结果"""
    cmd = ["perf", "stat", "-a", "-e", "cache-misses,cycles,instructions", "sleep", "10"]

    if host is None:
        # 本地执行
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                check=True
            )
            return _parse_stat(completed.stderr)

    # 远程执行
    config = CacheMissAuditConfig().get_config()
    target_host = None
    for h in config.public_config.remote_hosts:
        if host.strip() == h.name or host.strip() == h.host:
            target_host = h
            break
    if not target_host:
        if config.public_config.language == LanguageEnum.ZH:
            raise ValueError(f"未找到远程主机: {host}")
        else:
            raise ValueError(f"Remote host not found: {host}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=target_host.host,
        port=getattr(target_host, "port", 22),
        username=getattr(target_host, "username", None),
        password=getattr(target_host, "password", None),
        key_filename=getattr(target_host, "ssh_key_path", None),
        timeout=10
    )

    try:
        perf_cmd_str = " ".join(f"'{c}'" if " " in c else c for c in cmd)
        stdin, stdout, stderr = client.exec_command(perf_cmd_str)
        stdin.close()
        exit_code = stdout.channel.recv_exit_status()
        stat_output = stderr.read().decode("utf-8")

        if exit_code != 0 and not stat_output:
            raise RuntimeError(f"Remote perf stat failed, exit={exit_code}")

        return _parse_stat(stat_output)
    finally:
        client.close()


def _parse_stat(raw: str) -> Dict[str, Any]:
    """
    解析示例片段：
         3,361,887      cache-misses
       792,941,840      cycles
       292,432,459      instructions    # 0.37 insn per cycle
    """
    pat = re.compile(r"^\s*([\d,]+)\s+(cache-misses|cycles|instructions)", re.M)
    hit = {k: 0 for k in ("cache-misses", "cycles", "instructions")}
    for num, key in pat.findall(raw):
        hit[key] = int(num.replace(",", ""))

    ipc_match = re.search(r"#\s*([\d.]+)\s*insn per cycle", raw)
    ipc = float(ipc_match.group(1)) if ipc_match else 0.0

    sec_match = re.search(r"(\d+\.\d+)\s+seconds time elapsed", raw)
    seconds = float(sec_match.group(1)) if sec_match else 10.0

    return {
        "cache_misses": hit["cache-misses"],
        "cycles": hit["cycles"],
        "instructions": hit["instructions"],
        "ipc": ipc,
        "seconds": seconds
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
