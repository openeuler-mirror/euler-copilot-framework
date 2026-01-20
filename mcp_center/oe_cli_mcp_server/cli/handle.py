import logging
import os
import subprocess
import sys

import requests  # 新增：导入 requests 库（用于 HTTP 调用）

from oe_cli_mcp_server.server import config
# 新增：FastAPI 服务地址（和 api_server.py 配置一致，端口 12556）
FASTAPI_BASE_URL = f"http://127.0.0.1:{config.fastapi_port}"

# 路径配置（直接硬编码，简化）
PUBLIC_CONFIG_PATH = "config/private/mcp_server"

logger = logging.getLogger(__name__)

def send_http_request(action: str, params: dict = None):
    """调用 FastAPI 接口（替代原 Socket 调用）"""
    try:
        if action == "add":
            url = f"{FASTAPI_BASE_URL}/package/add"
            # 适配接口：只传 value 参数，移除 type
            response = requests.post(url, params={"value": params.get("value")})
        elif action == "remove":
            url = f"{FASTAPI_BASE_URL}/package/remove"
            # 适配接口：只传 value 参数，移除 type
            response = requests.post(url, params={"value": params.get("value")})
        elif action == "list":
            url = f"{FASTAPI_BASE_URL}/package/list"
            response = requests.get(url)
        elif action == "init":
            url = f"{FASTAPI_BASE_URL}/package/init"
            response = requests.post(url)
        else:
            return {"success": False, "message": f"不支持的操作：{action}"}

        response.raise_for_status()  # 抛出 HTTP 错误（如 404、500）
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"接口调用失败：{str(e)}"}

# -------------------------- 工具包操作 --------------------------
def handle_add(pkg_input):
    """处理 -add 命令"""
    if os.path.isfile(pkg_input) and pkg_input.endswith(".zip"):
        # 移除 type 参数，只传 value
        params = {"value": os.path.abspath(pkg_input)}
    else:
        print(f"❌ 不支持的包类型：{pkg_input}（仅支持 zip 文件）")
        raise SystemExit(1)

    result = send_http_request("add", params)
    print(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
    return result["success"]

def handle_remove(pkg_input):
    """处理 -remove 命令"""
    # 移除 type 参数，只传 value
    params = {"value": pkg_input}

    # 替换：send_socket_request → send_http_request
    result = send_http_request("remove", params)
    print(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")

    # 使用 API 重启而非系统命令（更轻量，避免权限问题）
    if result["success"]:
        print("\n🔄 正在重启服务使变更生效...")
        result["success"] = handle_restart()

    return result["success"]

def handle_tool():
    """处理 -tool 命令"""
    # 替换：send_socket_request → send_http_request
    result = send_http_request("list")
    if not result["success"]:
        print(f"❌ {result['message']}")
        return False

    # 适配 FastAPI 接口返回结构
    print(f"\n📋 当前已加载工具包（共{result['data']['total_packages']}个，总函数数：{result['data']['total_functions']}）：")
    for pkg, funcs in result["data"]["pkg_funcs"].items():
        print(f"- 📦 {pkg}：{len(funcs)}个工具")
        if funcs:
            print(f"  └─ 🛠️ {', '.join(funcs)}")
    return True

def handle_init():
    """处理 -init 命令"""
    # 替换：send_socket_request → send_http_request
    result = send_http_request("init")
    print(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")

    # 使用 API 重启而非系统命令
    if result["success"]:
        print("\n🔄 正在重启服务使初始化生效...")
        result["success"] = handle_restart()

    return result["success"]

# -------------------------- 服务操作 --------------------------
def handle_start():
    """处理 -start 命令"""
    try:
        subprocess.run(["sudo", "systemctl", "start", "oe-mcp"], check=True)
        print("✅ 服务启动成功")
        return True
    except Exception as e:
        print(f"❌ 启动失败：{str(e)}")
        return False

def handle_stop():
    """处理 -stop 命令"""
    try:
        subprocess.run(["sudo", "systemctl", "stop", "oe-mcp"], check=True)
        print("✅ 服务终止成功")
        return True
    except Exception as e:
        print(f"❌ 终止失败：{str(e)}")
        return False

def handle_restart():
    """处理 -restart 命令"""
    """处理 -restart 命令"""
    try:
        subprocess.run(["sudo", "systemctl", "restart", "oe-mcp"], check=True)
        print("✅ 服务重启成功")
        return True
    except Exception as e:
        print(f"❌ 重启失败：{str(e)}")
        return False

def handle_log():
    """处理 -log 命令"""
    try:
        subprocess.run(["sudo", "journalctl", "-u", "oe-mcp", "-f"], check=True)
    except KeyboardInterrupt:
        print("\n📌 日志查看退出")
    except Exception as e:
        print(f"❌ 查看失败：{str(e)}")
    return True
