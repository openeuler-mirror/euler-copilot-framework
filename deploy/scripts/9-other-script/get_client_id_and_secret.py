"""
获取认证信息
"""
import json
import sys
import requests
import urllib3
import subprocess

urllib3.disable_warnings()


def get_service_cluster_ip(namespace, service_name):
    cmd = ["kubectl", "get", "service", service_name, "-n", namespace, "-o", "json"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # 增强错误处理
    if result.returncode != 0:
        error_msg = result.stderr.decode().strip()
        print(f"获取服务信息失败: [命名空间: {namespace}] [服务名: {service_name}]")
        print(f"Kubectl错误详情: {error_msg}")

        # 常见错误提示
        if "NotFound" in error_msg:
            print("→ 请检查：")
            print("  1. 服务是否部署完成（kubectl get pods -n {namespace}）")
            print("  2. 服务名称是否拼写正确")
            print("  3. 是否在正确的Kubernetes上下文环境中")
    
    # 解析JSON输出
    service_info = json.loads(result.stdout.decode())
    
    # 从解析后的JSON中获取Cluster IP
    cluster_ip = service_info['spec'].get('clusterIP', 'No Cluster IP found')
    return cluster_ip

def get_user_token(auth_hub_url, username="administrator", password="changeme"):
    url = auth_hub_url + "/oauth2/manager-login"
    payload = {
        "password": password,
        "username": username,
    }
    headers = {
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
        response.raise_for_status()  # 触发HTTPError异常如果状态码不是2xx
        response_data = response.json()
        
        # 检查响应结构是否包含data.user_token
        if "data" in response_data and "user_token" in response_data["data"]:
            return response_data["data"]["user_token"]
        else:
            print("错误：响应中缺少预期的数据结构")
            print("完整响应内容：", json.dumps(response_data, indent=2))
            sys.exit(1)
            
    except requests.exceptions.HTTPError as e:
        print(f"登录请求失败，HTTP状态码：{response.status_code}")
        print("响应内容：", response.text)
        sys.exit(1)
    except json.JSONDecodeError:
        print("错误：无法解析响应为JSON")
        print("原始响应：", response.text)
        sys.exit(1)
    except Exception as e:
        print(f"发生未知错误：{str(e)}")
        sys.exit(1)


def register_app(auth_hub_url, user_token, client_name, client_url, redierct_urls):
    url = auth_hub_url + "/oauth2/applications/register"
    payload = {
            "client_name":client_name,
            "client_uri":client_url,
            "redirect_uris":redierct_urls,
            "skip_authorization":True,
            "register_callback_uris":[],
            "logout_callback_uris":[],
            "scope":["email","phone","username","openid","offline_access"],
            "grant_types":["authorization_code"],
            "response_types":["code"],
            "token_endpoint_auth_method":"none"
    }
    headers = {
        "Authorization": user_token,
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

def get_client_secret(auth_hub_url, user_token):
    url = auth_hub_url + "/oauth2/applications"
    headers = {
        "Authorization": user_token,
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        apps_data = response.json()
        
        # 确保响应结构正确
        if "data" in apps_data and "applications" in apps_data["data"]:
            for app in apps_data["data"]["applications"]:
                if app.get("client_metadata", {}).get("client_name") == "EulerCopilot":
                    return {
                        "client_id": app["client_info"]["client_id"],
                        "client_secret": app["client_info"]["client_secret"]
                    }
            return {"error": "Application not found"}
        else:
            print("错误：应用列表响应结构异常")
            print("完整响应：", json.dumps(apps_data, indent=2))
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"获取客户端凭证失败：{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    namespace = "euler-copilot"
    service_name = "authhub-web-service"

    print(f"正在查询服务信息: [命名空间: {namespace}] [服务名: {service_name}]")
    cluster_ip = get_service_cluster_ip(namespace, service_name)

    # 增加更明确的错误提示
    if not cluster_ip or cluster_ip == 'No Cluster IP found':
        print(f"无法获取ClusterIP，可能原因：")
        print("1. 服务类型不是ClusterIP（可能是NodePort/LoadBalancer）")
        print("2. 服务尚未分配IP（查看状态: kubectl get svc/{service_name} -n {namespace} -w）")
        sys.exit(1)

    print("\n请填写应用注册信息（直接回车使用默认值）") 
    # 注册应用
    client_name = input(f"请输入 client_name (默认：EulerCopilot)：").strip() or "EulerCopilot"
    client_url = input(f"请输入 client_url (默认：https://www.eulercopilot.local)：").strip() or "https://www.eulercopilot.local"

    redirect_input = input(
            f"请输入 redirect_urls (逗号分隔，默认：https://www.eulercopilot.local/api/auth/login)："
).strip()
    if redirect_input:
        redirect_urls = [url.strip() for url in redirect_input.split(",")]
    else:
        redirect_urls = ["https://www.eulercopilot.local/api/auth/login"]

    auth_hub_url = f"http://{cluster_ip}:8000"
    user_token = get_user_token(auth_hub_url)
    
    # 注册应用
    register_app(auth_hub_url, user_token, client_name, client_url, redirect_urls)
    
    # 获取客户端凭证
    client_info = get_client_secret(auth_hub_url, user_token)  # 传递user_token
    if "error" in client_info:
        print(client_info["error"])
        sys.exit(1)

    print(f"client_id: {client_info['client_id']}")
    print(f"client_secret: {client_info['client_secret']}")
