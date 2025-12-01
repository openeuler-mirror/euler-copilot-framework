import socket
import json
import logging
from typing import Dict, Any

# Socket配置（直接硬编码，简化配置）
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 8003
SOCKET_TIMEOUT = 5

logger = logging.getLogger(__name__)

def send_socket_request(action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """发送Socket请求到服务端（极简封装，失败直接返回错误）"""
    params = params or {}
    request = json.dumps({"action": action, "params": params}, ensure_ascii=False).encode("utf-8")

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(SOCKET_TIMEOUT)
        client.connect((SOCKET_HOST, SOCKET_PORT))
        client.send(request)
        response = json.loads(client.recv(4096).decode("utf-8"))
        client.close()
        return response
    except socket.timeout:
        return {"success": False, "message": "连接服务超时"}
    except ConnectionRefusedError:
        return {"success": False, "message": "服务未启动，请先执行 -start"}
    except Exception as e:
        logger.error(f"Socket通信失败：{str(e)}")
        return {"success": False, "message": f"通信失败：{str(e)}"}