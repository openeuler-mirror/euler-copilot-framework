"""
Get Authentication Information
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
        print(f"Failed to get service info: [Namespace: {namespace}] [Service: {service_name}]")
        print(f"Kubectl error details: {error_msg}")

        if "NotFound" in error_msg:
            print("→ Please check:")
            print(f"  1. Whether the service is deployed (kubectl get pods -n {namespace})")
            print(f"  2. Whether the service name is spelled correctly")
            print(f"  3. Whether you are in the correct Kubernetes context")
        sys.exit(1)

    service_info = json.loads(result.stdout.decode())
    return service_info['spec'].get('clusterIP', 'No Cluster IP found')

def get_user_token(authhub_web_url, username="administrator", password="changeme"):
    url = authhub_web_url + "/oauth2/manager-login"
    response = requests.post(
        url,
        json={"password": password, "username": username},
        headers={"Content-Type": "application/json"},
        verify=False,
        timeout=10
    )
    response.raise_for_status()
    return response.json()["data"]["user_token"]

def find_existing_app(authhub_web_url, user_token, client_name):
    response = requests.get(
        authhub_web_url + "/oauth2/applications",
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

        if any(str(name).lower() == client_name.lower() for name in candidate_names if name):
            return app["client_info"]["client_id"]
    return None

def register_or_update_app(authhub_web_url, user_token, client_name, client_url, redirect_urls):
    client_id = find_existing_app(authhub_web_url, user_token, client_name)

    if client_id:
        # Update existing application
        print(f"Found existing application [Name: {client_name}], updating...")
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
        return response.json()["data"]
    else:
        # Register new application
        print(f"No existing application found [Name: {client_name}], registering new application...")
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
        return response.json()["data"]

def get_client_secret(authhub_web_url, user_token, client_id):
    response = requests.get(
        f"{authhub_web_url}/oauth2/applications/{client_id}",
        headers={"Authorization": user_token, "Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    app_data = response.json()
    return {
        "client_id": app_data["data"]["client_info"]["client_id"],
        "client_secret": app_data["data"]["client_info"]["client_secret"]
    }

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("eulercopilot_address", help="EulerCopilot frontend address (default:http://172.0.0.1:30080)")
    args = parser.parse_args()

    # Get service information
    namespace = "euler-copilot"
    service_name = "authhub-web-service"
    print(f"Querying service info: [Namespace: {namespace}] [Service: {service_name}]")
    cluster_ip = get_service_cluster_ip(namespace, service_name)
    authhub_web_url = f"http://{cluster_ip}:8000"

    # Generate fixed URLs
    client_url = f"{args.eulercopilot_address}"
    redirect_urls = [f"{args.eulercopilot_address}/api/auth/login"]
    client_name = "EulerCopilot"  # Set fixed default value

    # Authentication process
    try:
        print("\nGetting user token...")
        user_token = get_user_token(authhub_web_url)
        print("✓ User token obtained successfully")

        print(f"\nProcessing application [Name: {client_name}]...")
        app_info = register_or_update_app(authhub_web_url, user_token, client_name, client_url, redirect_urls)
        print("✓ Application processed successfully")

        print(f"\nQuerying client credentials [ID: {app_info['client_info']['client_id']}]...")
        client_info = get_client_secret(authhub_web_url, user_token, app_info["client_info"]["client_id"])

        print("\n✓ Authentication information obtained successfully:")
        print(f"client_id: {client_info['client_id']}")
        print(f"client_secret: {client_info['client_secret']}")

    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP Error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)
