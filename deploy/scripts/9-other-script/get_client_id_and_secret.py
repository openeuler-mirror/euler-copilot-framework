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

def get_user_token(authhub_web_url, username="openEuler", password="changeme"):
    url = authhub_web_url + "/oauth2/manager-login"
    response = requests.post(
        url,
        json={"password": password, "username": username},
        headers={"Content-Type": "application/json"},
        verify=False,
        timeout=10
    )
    response.raise_for_status()
    
    # 添加响应调试信息
    response_data = response.json()
    print(f"登录API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
    
    if "data" not in response_data:
        raise ValueError(f"登录响应中缺少 'data' 字段。完整响应: {response_data}")
    
    if "user_token" not in response_data["data"]:
        raise ValueError(f"登录响应的data字段中缺少 'user_token'。data内容: {response_data['data']}")
    
    return response_data["data"]["user_token"]

def find_existing_app(authhub_web_url, user_token, client_name):
    response = requests.get(
        authhub_web_url + "/oauth2/applications",
        headers={"Authorization": user_token, "Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    apps_data = response.json()
    
    # 添加响应调试信息
    print(f"应用列表API响应: {json.dumps(apps_data, indent=2, ensure_ascii=False)}")
    
    if "data" not in apps_data:
        raise ValueError(f"应用列表响应中缺少 'data' 字段。完整响应: {apps_data}")
    
    if "applications" not in apps_data["data"]:
        raise ValueError(f"应用列表响应的data字段中缺少 'applications'。data内容: {apps_data['data']}")

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

        if any(str(name).lower() == client_name.lower() for name in candidate_names if name):
            return app["client_info"]["client_id"]
    return None

def register_or_update_app(authhub_web_url, user_token, client_name, client_url, redirect_urls):
    client_id = find_existing_app(authhub_web_url, user_token, client_name)
    
    if client_id:
        # 更新现有应用
        print(f"发现已存在应用 [名称: {client_name}], 正在更新...")
        url = f"{authhub_web_url}/oauth2/applications/{client_id}"
        response = requests.put(
            url,
            json={
                "client_uri": client_url,
                "redirect_uris": redirect_urls,
                "register_callback_uris": [],
                "logout_callback_uris": [],
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
        
        # 添加响应调试信息
        response_data = response.json()
        print(f"更新应用API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        if "data" not in response_data:
            raise ValueError(f"更新应用响应中缺少 'data' 字段。完整响应: {response_data}")
        
        return response_data["data"]
    else:
        # 注册新应用
        print(f"未找到已存在应用 [名称: {client_name}], 正在注册新应用...")
        response = requests.post(
            authhub_web_url + "/oauth2/applications/register",
            json={
                "client_name": client_name,
                "client_uri": client_url,
                "redirect_uris": redirect_urls,
                "register_callback_uris": [],
                "logout_callback_uris": [],
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
        
        # 添加响应调试信息
        response_data = response.json()
        print(f"注册应用API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        if "data" not in response_data:
            raise ValueError(f"注册应用响应中缺少 'data' 字段。完整响应: {response_data}")
        
        return response_data["data"]

def get_client_secret(authhub_web_url, user_token, client_id):
    response = requests.get(
        f"{authhub_web_url}/oauth2/applications/{client_id}",
        headers={"Authorization": user_token, "Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    app_data = response.json()
    
    # 添加响应调试信息
    print(f"获取客户端凭证API响应: {json.dumps(app_data, indent=2, ensure_ascii=False)}")
    
    if "data" not in app_data:
        raise ValueError(f"获取客户端凭证响应中缺少 'data' 字段。完整响应: {app_data}")
    
    if "client_info" not in app_data["data"]:
        raise ValueError(f"获取客户端凭证响应的data字段中缺少 'client_info'。data内容: {app_data['data']}")
    
    client_info = app_data["data"]["client_info"]
    if "client_id" not in client_info or "client_secret" not in client_info:
        raise ValueError(f"client_info中缺少必要字段。client_info内容: {client_info}")
    
    return {
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"]
    }

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser()
    parser.add_argument("eulercopilot_address", help="EulerCopilot前端地址（默认:http://172.0.0.1:30080）")
    args = parser.parse_args()

    # 获取服务信息
    namespace = "euler-copilot"
    service_name = "authhub-web-service"
    print(f"正在查询服务信息: [命名空间: {namespace}] [服务名: {service_name}]")
    cluster_ip = get_service_cluster_ip(namespace, service_name)
    authhub_web_url = f"http://{cluster_ip}:8000"

    # 生成固定URL
    client_url = f"{args.eulercopilot_address}"
    redirect_urls = [f"{args.eulercopilot_address}/api/auth/login"]
    client_name = "EulerCopilot"  # 设置固定默认值

    # 认证流程
    try:
        print("\n正在获取用户令牌...")
        user_token = get_user_token(authhub_web_url)
        print("✓ 用户令牌获取成功")

        print(f"\n正在处理应用 [名称: {client_name}]...")
        app_info = register_or_update_app(authhub_web_url, user_token, client_name, client_url, redirect_urls)
        print("✓ 应用处理成功")

        print(f"\n正在查询客户端凭证 [ID: {app_info['client_info']['client_id']}]...")
        client_info = get_client_secret(authhub_web_url, user_token, app_info["client_info"]["client_id"])

        print("\n✓ 认证信息获取成功：")
        print(f"client_id: {client_info['client_id']}")
        print(f"client_secret: {client_info['client_secret']}")

    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP 错误: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)
