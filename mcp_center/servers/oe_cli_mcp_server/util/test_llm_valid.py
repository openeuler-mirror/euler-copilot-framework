import requests

def is_llm_config_valid(API_URL: str, API_KEY: str = "", MODEL_NAME: str = "") -> bool:
    """
    极简验证大模型配置是否通畅
    :param API_URL: 模型 API 地址
    :param API_KEY: 可选 API Key
    :param MODEL_NAME: 模型名
    :return: True=通畅，False=不通
    """
    try:
        # 极简请求体（满足接口最基本要求）
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "hi"}],  # 最短输入
            "max_tokens": 10,  # 最少生成字数，加快速度
            "temperature": 0.0
        }
        # 请求头
        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["Authorization"] = f"Bearer {API_KEY}"
        # 发送请求（超时 5 秒，快速失败）
        response = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=5,
            verify=False  # 忽略 SSL 证书校验（可选，简化验证）
        )
        # 只要状态码 2xx，且返回有 choices，就认为通
        return response.status_code == 200 and "choices" in response.json()
    except:
        # 任何异常都视为“不通”
        return False