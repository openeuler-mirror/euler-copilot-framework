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
    
    if result.returncode != 0:
        error_msg = result.stderr.decode().strip()
        print(f"获取服务信息失败: [命名空间: {namespace}] [服务名: {service_name}]")
        print(f"Kubectl错误详情: {error_msg}")

        if "NotFound" in error_msg:
            print("→ 请检查：")
            print(f"  1. 服务是否部署完成（kubectl get pods -n {namespace}）")
            print("  2. 服务名称是否拼写正确")
            print("  3. 是否在正确的Kubernetes上下文环境中")
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
    requests.post(
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
        headers={"Authorization": user_token, "Content-Type": "application/json"}
    )


def get_client_secret(auth_hub_url, user_token, target_client_name):
    response = requests.get(
        auth_hub_url + "/oauth2/applications",
        headers={"Authorization": user_token, "Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    apps_data = response.json()

    for app in apps_data["data"]["applications"]:
        # 处理 client_metadata 字段
        client_metadata = app.get("client_metadata") or {}
        if isinstance(client_metadata, str):
            try:
                client_metadata = json.loads(client_metadata)
            except json.JSONDecodeError:
                client_metadata = {}

        # 优先从 client_metadata 获取名称
        candidate_names = [
            client_metadata.get("client_name"),
            app.get("client_name"),
            app.get("client_info", {}).get("client_name")
        ]
        
        # 调试输出关键信息
        print(f"\n匹配进度 | 候选名称: {candidate_names} | 目标名称: {target_client_name}")

        # 不区分大小写匹配
        if any(str(name).lower() == target_client_name.lower() for name in candidate_names if name):
            return {
                "client_id": app["client_info"]["client_id"],
                "client_secret": app["client_info"]["client_secret"]
            }
    
    raise ValueError(f"未找到匹配应用，请检查 client_name 是否准确（尝试使用全小写名称）")


if __name__ == "__main__":
    # 获取服务信息
    namespace = "euler-copilot"
    service_name = "authhub-web-service"
    print(f"正在查询服务信息: [命名空间: {namespace}] [服务名: {service_name}]")
    cluster_ip = get_service_cluster_ip(namespace, service_name)
    auth_hub_url = f"http://{cluster_ip}:8000"

    # 用户输入
    print("\n请填写应用注册信息（直接回车使用默认值）")
    client_name = input("请输入 client_name (默认：EulerCopilot)：").strip() or "EulerCopilot"
    client_url = input("请输入 client_url (默认：https://www.eulercopilot.local)：").strip() or "https://www.eulercopilot.local"
    
    redirect_input = input(
        "请输入 redirect_urls (逗号分隔，默认：https://www.eulercopilot.local/api/auth/login)："
    ).strip()
    redirect_urls = [url.strip() for url in redirect_input.split(",")] if redirect_input else [
        "https://www.eulercopilot.local/api/auth/login"
    ]

    # 认证流程
    try:
        user_token = get_user_token(auth_hub_url)
        register_app(auth_hub_url, user_token, client_name, client_url, redirect_urls)
        client_info = get_client_secret(auth_hub_url, user_token, client_name)
        
        print("\n认证信息获取成功：")
        print(f"client_id: {client_info['client_id']}")
        print(f"client_secret: {client_info['client_secret']}")
    
    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)
