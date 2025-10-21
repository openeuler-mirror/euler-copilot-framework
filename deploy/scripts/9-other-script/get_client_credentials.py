#!/usr/bin/env python3
"""
获取认证信息 - 支持多种鉴权服务
支持的鉴权服务：
1. authHub - 通过API动态管理OAuth2应用
2. authelia - 通过配置文件管理OpenID Connect客户端
"""
import json
import sys
import requests
import urllib3
import subprocess
import argparse
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

urllib3.disable_warnings()

class AuthServiceBase:
    """鉴权服务基类"""
    
    def __init__(self, service_url: str, client_name: str, client_url: str, redirect_urls: list):
        self.service_url = service_url
        self.client_name = client_name
        self.client_url = client_url
        self.redirect_urls = redirect_urls
    
    def get_or_create_client(self) -> Dict[str, str]:
        """获取或创建客户端凭证"""
        raise NotImplementedError("子类必须实现此方法")

class AuthHubService(AuthServiceBase):
    """authHub服务实现"""
    
    def __init__(self, service_url: str, client_name: str, client_url: str, redirect_urls: list):
        super().__init__(service_url, client_name, client_url, redirect_urls)
        self.username = "openEuler"
        self.password = "changeme"
    
    def get_user_token(self) -> str:
        """获取用户令牌"""
        url = f"{self.service_url}/oauth2/manager-login"
        response = requests.post(
            url,
            json={"password": self.password, "username": self.username},
            headers={"Content-Type": "application/json"},
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        
        response_data = response.json()
        print(f"登录API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        if "data" not in response_data:
            raise ValueError(f"登录响应中缺少 'data' 字段。完整响应: {response_data}")
        
        if "user_token" not in response_data["data"]:
            raise ValueError(f"登录响应的data字段中缺少 'user_token'。data内容: {response_data['data']}")
        
        return response_data["data"]["user_token"]
    
    def find_existing_app(self, user_token: str) -> Optional[str]:
        """查找已存在的应用"""
        response = requests.get(
            f"{self.service_url}/oauth2/applications",
            headers={"Authorization": user_token, "Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        apps_data = response.json()
        
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

            if any(str(name).lower() == self.client_name.lower() for name in candidate_names if name):
                return app["client_info"]["client_id"]
        return None
    
    def register_or_update_app(self, user_token: str) -> Dict[str, Any]:
        """注册或更新应用"""
        client_id = self.find_existing_app(user_token)
        
        if client_id:
            # 更新现有应用
            print(f"发现已存在应用 [名称: {self.client_name}], 正在更新...")
            url = f"{self.service_url}/oauth2/applications/{client_id}"
            response = requests.put(
                url,
                json={
                    "client_uri": self.client_url,
                    "redirect_uris": self.redirect_urls,
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
            
            response_data = response.json()
            print(f"更新应用API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            
            if "data" not in response_data:
                raise ValueError(f"更新应用响应中缺少 'data' 字段。完整响应: {response_data}")
            
            return response_data["data"]
        else:
            # 注册新应用
            print(f"未找到已存在应用 [名称: {self.client_name}], 正在注册新应用...")
            response = requests.post(
                f"{self.service_url}/oauth2/applications/register",
                json={
                    "client_name": self.client_name,
                    "client_uri": self.client_url,
                    "redirect_uris": self.redirect_urls,
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
            
            response_data = response.json()
            print(f"注册应用API响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            
            if "data" not in response_data:
                raise ValueError(f"注册应用响应中缺少 'data' 字段。完整响应: {response_data}")
            
            return response_data["data"]
    
    def get_client_secret(self, user_token: str, client_id: str) -> Dict[str, str]:
        """获取客户端凭证"""
        response = requests.get(
            f"{self.service_url}/oauth2/applications/{client_id}",
            headers={"Authorization": user_token, "Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        app_data = response.json()
        
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
    
    def get_or_create_client(self) -> Dict[str, str]:
        """获取或创建客户端凭证"""
        print("\n正在获取用户令牌...")
        user_token = self.get_user_token()
        print("✓ 用户令牌获取成功")

        print(f"\n正在处理应用 [名称: {self.client_name}]...")
        app_info = self.register_or_update_app(user_token)
        print("✓ 应用处理成功")

        print(f"\n正在查询客户端凭证 [ID: {app_info['client_info']['client_id']}]...")
        client_info = self.get_client_secret(user_token, app_info["client_info"]["client_id"])
        
        return client_info

class AutheliaService(AuthServiceBase):
    """authelia服务实现"""
    
    def __init__(self, service_url: str, client_name: str, client_url: str, redirect_urls: list, config_path: str = None):
        super().__init__(service_url, client_name, client_url, redirect_urls)
        self.config_path = config_path or "/config/configuration.yml"
    
    def generate_client_secret(self) -> str:
        """生成客户端密钥"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))
    
    def get_or_create_client(self) -> Dict[str, str]:
        """获取或创建客户端凭证"""
        print(f"\n正在处理 authelia 客户端配置...")
        
        # 生成客户端ID和密钥
        client_id = self.client_name.lower().replace(' ', '-')
        client_secret = self.generate_client_secret()
        
        # 创建客户端配置
        client_config = {
            "client_id": client_id,
            "client_name": self.client_name,
            "client_secret": f"$plaintext${client_secret}",  # authelia支持明文密钥用于开发
            "public": False,
            "redirect_uris": self.redirect_urls,
            "scopes": ["openid", "profile", "email", "groups"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "authorization_policy": "two_factor"
        }
        
        print("✓ authelia 客户端配置生成完成")
        print("\n请将以下配置添加到 authelia 配置文件中：")
        print("=" * 60)
        print("identity_providers:")
        print("  oidc:")
        print("    clients:")
        print(f"      - client_id: '{client_id}'")
        print(f"        client_name: '{self.client_name}'")
        print(f"        client_secret: '$plaintext${client_secret}'")
        print("        public: false")
        print("        redirect_uris:")
        for uri in self.redirect_urls:
            print(f"          - '{uri}'")
        print("        scopes:")
        print("          - 'openid'")
        print("          - 'profile'")
        print("          - 'email'")
        print("          - 'groups'")
        print("        grant_types:")
        print("          - 'authorization_code'")
        print("        response_types:")
        print("          - 'code'")
        print("        authorization_policy: 'two_factor'")
        print("=" * 60)
        print("\n注意：配置完成后需要重启 authelia 服务以使配置生效。")
        
        return {
            "client_id": client_id,
            "client_secret": client_secret
        }

def get_service_cluster_ip(namespace: str, service_name: str) -> str:
    """获取Kubernetes服务的ClusterIP"""
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

def detect_auth_service() -> Tuple[str, str]:
    """检测已部署的鉴权服务"""
    services_to_check = [
        ("euler-copilot", "authhub-web-service", "authHub"),
        ("authelia", "authelia-service", "authelia"),
        ("default", "authelia", "authelia")
    ]
    
    available_services = []
    
    for namespace, service_name, service_type in services_to_check:
        try:
            cmd = ["kubectl", "get", "service", service_name, "-n", namespace, "--no-headers"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if result.returncode == 0:
                available_services.append((namespace, service_name, service_type))
        except (subprocess.TimeoutExpired, Exception):
            continue
    
    return available_services

def choose_auth_service() -> Tuple[str, str, str]:
    """让用户选择鉴权服务"""
    print("正在检测已部署的鉴权服务...")
    available_services = detect_auth_service()
    
    if not available_services:
        print("❌ 未检测到任何已部署的鉴权服务")
        print("支持的服务：authHub, authelia")
        sys.exit(1)
    
    print(f"\n检测到 {len(available_services)} 个可用的鉴权服务：")
    for i, (namespace, service_name, service_type) in enumerate(available_services, 1):
        print(f"  {i}. {service_type} (命名空间: {namespace}, 服务: {service_name})")
    
    while True:
        try:
            choice = input(f"\n请选择要使用的鉴权服务 (1-{len(available_services)}): ").strip()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(available_services):
                namespace, service_name, service_type = available_services[choice_idx]
                print(f"✓ 已选择: {service_type}")
                return namespace, service_name, service_type
            else:
                print(f"请输入 1 到 {len(available_services)} 之间的数字")
        except (ValueError, KeyboardInterrupt):
            print("\n操作已取消")
            sys.exit(1)

def create_auth_service(service_type: str, service_url: str, client_name: str, client_url: str, redirect_urls: list) -> AuthServiceBase:
    """创建鉴权服务实例"""
    if service_type.lower() == "authhub":
        return AuthHubService(service_url, client_name, client_url, redirect_urls)
    elif service_type.lower() == "authelia":
        return AutheliaService(service_url, client_name, client_url, redirect_urls)
    else:
        raise ValueError(f"不支持的鉴权服务类型: {service_type}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="获取认证信息 - 支持多种鉴权服务")
    parser.add_argument("eulercopilot_address", help="EulerCopilot前端地址（例如: https://10.211.55.10）")
    parser.add_argument("--client-name", default="EulerCopilot", help="客户端应用名称（默认: EulerCopilot）")
    args = parser.parse_args()

    print("=" * 60)
    print("EulerCopilot 认证信息获取工具")
    print("支持的鉴权服务: authHub, authelia")
    print("=" * 60)

    # 选择鉴权服务
    namespace, service_name, service_type = choose_auth_service()
    
    # 获取服务信息
    print(f"\n正在查询服务信息: [命名空间: {namespace}] [服务名: {service_name}]")
    
    if service_type.lower() == "authhub":
        cluster_ip = get_service_cluster_ip(namespace, service_name)
        service_url = f"http://{cluster_ip}:8000"
    else:  # authelia
        cluster_ip = get_service_cluster_ip(namespace, service_name)
        service_url = f"http://{cluster_ip}:9091"
    
    print(f"✓ 服务地址: {service_url}")

    # 生成配置
    client_url = args.eulercopilot_address
    redirect_urls = [f"{args.eulercopilot_address}/api/auth/login"]
    client_name = args.client_name

    print(f"\n配置信息:")
    print(f"  鉴权服务类型: {service_type}")
    print(f"  鉴权服务地址: {service_url}")
    print(f"  EulerCopilot地址: {client_url}")
    print(f"  客户端名称: {client_name}")
    print(f"  回调地址: {redirect_urls}")

    # 创建鉴权服务实例并获取凭证
    try:
        auth_service = create_auth_service(service_type, service_url, client_name, client_url, redirect_urls)
        client_info = auth_service.get_or_create_client()

        print(f"\n✓ 认证信息获取成功：")
        print(f"  鉴权服务类型: {service_type}")
        print(f"  鉴权服务地址: {service_url}")
        print(f"  client_id: {client_info['client_id']}")
        print(f"  client_secret: {client_info['client_secret']}")
        
        if service_type.lower() == "authelia":
            print(f"\n📝 请按照上述说明将配置添加到 authelia 配置文件中并重启服务。")

    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP 错误: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
