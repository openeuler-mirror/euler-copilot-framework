"""
获取认证信息
"""
import json
import sys
import requests
import urllib3
import subprocess
import argparse

urllib3.disable_warnings()

def get_service_cluster_ip(namespace, service_name):
    cmd = ["kubectl", "get", "service", service_name, "-n", namespace, "-o", "json"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        error_msg = result.stderr.decode().strip()
        print(f"获取服务信息失败: [命名空间: {namespace}] [服务名: {service_name}]")
        print(f"Kubectl错误详情: {error_msg}")

        if "NotFound" in error_msg:
            print("→ 请检查：")
            print(f"  1. 服务是否部署完成（kubectl get pods -n {namespace}）")
            print(f"  2. 服务名称是否拼写正确")
            print(f"  3. 是否在正确的Kubernetes上下文环境中")
        sys.exit(1)

    service_info = json.loads(result.stdout.decode())
    return service_info['spec'].get('clusterIP', 'No Cluster IP found')

def get_user_token(auth_hub_url, username="administrator", password="changeme"):
    url = auth_hub_url + "/oauth2/manager-login"
    response = requests.post(
        url,
        json={"password": password, "username": username},
        headers={"Content-Type": "application/json"},
        verify=False,
        timeout=10
    )
    response.raise_for_status()
    return response.json()["data"]["user_token"]

def register_app(auth_hub_url, user_token, client_name, client_url, redirect_urls):
    response = requests.post(
        auth_hub_url + "/oauth2/applications/register",
        json={
            "client_name": client_name,
            "client_uri": client_url,
            "redirect_uris": redirect_urls,
            "skip_authorization": True,
            "scope": ["email", "phone", "username", "openid", "offline_access"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none"
        },
        headers={"Authorization": user_token, "Content-Type": "application/json"},
        verify=False
    )
    response.raise_for_status()

def get_client_secret(auth_hub_url, user_token, target_client_name):
    response = requests.get(
        auth_hub_url + "/oauth2/applications",
        headers={"Authorization": user_token, "Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    apps_data = response.json()

    for app in apps_data["data"]["applications"]:
        client_metadata = app.get("client_metadata") or {}
        if isinstance(client_metadata, str):
            try:
                client_metadata = json.loads(client_metadata)
            except json.JSONDecodeError:
                client_metadata = {}

        candidate_names = [
            client_metadata.get("client_name"),
            app.get("client_name"),
            app.get("client_info", {}).get("client_name")
        ]

        if any(str(name).lower() == target_client_name.lower() for name in candidate_names if name):
            return {
                "client_id": app["client_info"]["client_id"],
                "client_secret": app["client_info"]["client_secret"]
            }

    raise ValueError(f"未找到匹配应用，请检查 client_name 是否准确（尝试使用全小写名称）")

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser()
    parser.add_argument("eulercopilot_domain", help="EulerCopilot域名（例如：example.com）")
    args = parser.parse_args()

    # 获取服务信息
    namespace = "euler-copilot"
    service_name = "authhub-web-service"
    print(f"正在查询服务信息: [命名空间: {namespace}] [服务名: {service_name}]")
    cluster_ip = get_service_cluster_ip(namespace, service_name)
    auth_hub_url = f"http://{cluster_ip}:8000"

    # 生成固定URL
    client_url = f"https://{args.eulercopilot_domain}"
    redirect_urls = [f"https://{args.eulercopilot_domain}/api/auth/login"]
    client_name = "EulerCopilot"  # 设置固定默认值

    # 认证流程
    try:
        print("\n正在获取用户令牌...")
        user_token = get_user_token(auth_hub_url)
        print("✓ 用户令牌获取成功")

        print(f"\n正在注册应用 [名称: {client_name}]...")
        register_app(auth_hub_url, user_token, client_name, client_url, redirect_urls)
        print("✓ 应用注册成功")

        print(f"\n正在查询客户端凭证 [名称: {client_name}]...")
        client_info = get_client_secret(auth_hub_url, user_token, client_name)

        print("\n✓ 认证信息获取成功：")
        print(f"client_id: {client_info['client_id']}")
        print(f"client_secret: {client_info['client_secret']}")

    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP 错误: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)
