import logging
import os
import subprocess
import toml
import requests  # 新增：导入 requests 库（用于 HTTP 调用）
from mcp_tools.tool_type import ToolType
from util.get_project_root import get_project_root
from util.test_llm_valid import is_llm_config_valid

# 新增：FastAPI 服务地址（和 api_server.py 配置一致，端口 12556）
FASTAPI_BASE_URL = "http://127.0.0.1:12556"

# 路径配置（直接硬编码，简化）
PUBLIC_CONFIG_PATH = os.path.join(get_project_root(), "config/public_config.toml")

logger = logging.getLogger(__name__)

# 新增：替代 send_socket_request 的 HTTP 调用函数
def send_http_request(action: str, params: dict = None):
    """调用 FastAPI 接口（替代原 Socket 调用）"""
    try:
        if action == "add":
            url = f"{FASTAPI_BASE_URL}/tool/add"
            response = requests.post(url, params=params)
        elif action == "remove":
            url = f"{FASTAPI_BASE_URL}/tool/remove"
            response = requests.post(url, params=params)
        elif action == "list":
            url = f"{FASTAPI_BASE_URL}/tool/list"
            response = requests.get(url)
        elif action == "init":
            url = f"{FASTAPI_BASE_URL}/tool/init"
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
    type_map = {"智能运维": ToolType.BASE.value, "智算调优": ToolType.AI.value,
                "通算调优": ToolType.CAL.value, "镜像运维": ToolType.MIRROR.value,
                "个性化": ToolType.PERSONAL.value,"知识库": ToolType.RAG.value}

    if pkg_input in type_map:
        params = {"type": "system", "value": type_map[pkg_input]}
    elif os.path.isfile(pkg_input) and pkg_input.endswith(".zip"):
        params = {"type": "custom", "value": os.path.abspath(pkg_input)}
    else:
        print(f"❌ 不支持的包类型：{pkg_input}")
        raise SystemExit(1)

    # 替换：send_socket_request → send_http_request
    result = send_http_request("add", params)
    print(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
    return result["success"]

def handle_remove(pkg_input):
    """处理 -remove 命令"""
    type_map = {"智能运维": ToolType.BASE.value, "智算调优": ToolType.AI.value,
                "通算调优": ToolType.CAL.value, "镜像运维": ToolType.MIRROR.value,
                "个性化": ToolType.PERSONAL.value,"知识库": ToolType.RAG.value}

    params = {"type": "system" if pkg_input in type_map else "custom",
              "value": type_map.get(pkg_input, pkg_input)}
    # 替换：send_socket_request → send_http_request
    result = send_http_request("remove", params)
    print(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
    return result["success"]

def handle_tool():
    """处理 -tool 命令"""
    # 替换：send_socket_request → send_http_request
    result = send_http_request("list")
    if not result["success"]:
        print(f"❌ {result['message']}")
        return False

    # 注意：FastAPI 接口返回的结构是 data.pkg_funcs 和 data.total_packages（需调整）
    print(f"\n📋 当前已加载工具包（共{result['data']['total_packages']}个）：")
    for pkg, funcs in result["data"]["pkg_funcs"].items():
        print(f"- {pkg}：{len(funcs)}个工具 → {', '.join(funcs)}")
    return True

def handle_init():
    """处理 -init 命令"""
    # 替换：send_socket_request → send_http_request
    result = send_http_request("init")
    print(f"✅ {result['message']}" if result["success"] else f"❌ {result['message']}")
    return result["success"]

# -------------------------- 服务操作 --------------------------
def handle_start():
    """处理 -start 命令"""
    try:
        subprocess.run(["sudo", "systemctl", "start", "mcp-server"], check=True)
        print("✅ 服务启动成功")
        return True
    except Exception as e:
        print(f"❌ 启动失败：{str(e)}")
        return False

def handle_stop():
    """处理 -stop 命令"""
    try:
        subprocess.run(["sudo", "systemctl", "stop", "mcp-server"], check=True)
        print("✅ 服务终止成功")
        return True
    except Exception as e:
        print(f"❌ 终止失败：{str(e)}")
        return False

def handle_restart():
    """处理 -restart 命令"""
    try:
        subprocess.run(["sudo", "systemctl", "restart", "mcp-server"], check=True)
        print("✅ 服务重启成功")
        return True
    except Exception as e:
        print(f"❌ 重启失败：{str(e)}")
        return False

def handle_log():
    """处理 -log 命令"""
    try:
        subprocess.run(["sudo", "journalctl", "-u", "mcp-server", "-f"], check=True)
    except KeyboardInterrupt:
        print("\n📌 日志查看退出")
    except Exception as e:
        print(f"❌ 查看失败：{str(e)}")
    return True

# -------------------------- 配置操作 --------------------------
def handle_llm(model, apikey, name):
    """处理 -llm 命令"""
    if not all([model, apikey, name]):
        print("❌ 缺少参数：--model、--apikey、--name 必须同时指定")
        return False

    if not is_llm_config_valid(model, apikey, name):
        print("❌ 大模型校验失败")
        return False

    try:
        with open(PUBLIC_CONFIG_PATH, "r") as f:
            config = toml.load(f)
        config["llm_remote"] = model
        config["llm_api_key"] = apikey
        config["llm_model"] = name
        with open(PUBLIC_CONFIG_PATH, "w") as f:
            toml.dump(config, f)

        subprocess.run(["sudo", "systemctl", "restart", "mcp-server"], check=True)
        print(f"✅ 大模型配置成功（模型：{name}）")
        return True
    except Exception as e:
        print(f"❌ 配置失败：{str(e)}")
        return False

def handle_config(key_value):
    """处理 -config 命令"""
    if "=" not in key_value:
        print("❌ 格式错误：需为 键=值（如 -config port=8002）")
        return False

    key, value = key_value.split("=", 1)
    supported = ["language", "max_tokens", "temperature", "port"]
    if key not in supported:
        print(f"❌ 不支持的键：{key}（支持：{', '.join(supported)}）")
        return False

    try:
        with open(PUBLIC_CONFIG_PATH, "r") as f:
            config = toml.load(f)
        # 类型转换
        if key in ["max_tokens", "port"]:
            value = int(value)
        elif key == "temperature":
            value = float(value)
        config[key] = value
        with open(PUBLIC_CONFIG_PATH, "w") as f:
            toml.dump(config, f)

        if key == "port":
            subprocess.run(["sudo", "systemctl", "restart", "mcp-server"], check=True)
            print(f"✅ 配置 {key}={value}（已重启服务）")
        else:
            print(f"✅ 配置 {key}={value}（下次重启生效）")
        return True
    except Exception as e:
        print(f"❌ 配置失败：{str(e)}")
        return False