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
    response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)
    if response.status_code == 200:
        user_token = response.json()["data"]["user_token"]
    return user_token

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


def get_client_secret(auth_hub_url, user_token):  # 修改参数列表
    url = auth_hub_url + "/oauth2/applications"
    headers = {
        "Authorization": user_token,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    for app in response.json()['data']["applications"]:
        if app["client_metadata"]["client_name"] == "EulerCopilot":
            return {
                "client_id": app["client_info"]["client_id"],
                "client_secret": app["client_info"]["client_secret"]
            }
    return {"error": "Application not found"}

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

    auth_hub_url = f"http://{cluster_ip}:8000"
    user_token = get_user_token(auth_hub_url)
    
    # 注册应用
    client_name = "EulerCopilot"
    client_url = "https://www.eulercopilot.local"
    redirect_urls = ["https://www.eulercopilot.local/api/auth/login"]
    register_app(auth_hub_url, user_token, client_name, client_url, redirect_urls)
    
    # 获取客户端凭证
    client_info = get_client_secret(auth_hub_url, user_token)  # 传递user_token
    if "error" in client_info:
        print(client_info["error"])
        sys.exit(1)

    print(f"client_id: {client_info['client_id']}")
    print(f"client_secret: {client_info['client_secret']}")
