"""
获取认证信息
"""
import json

import requests
import urllib3

urllib3.disable_warnings()

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

def get_client_secret(auth_hub_url):
    url = auth_hub_url + "/oauth2/applications"
    headers = {
        "Authorization": user_token,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    for app in response.json()['data']["applications"]:
        if app["client_metadata"]["client_name"] == "EulerCopilot":
            return {
                "client_id":app["client_info"]["client_id"],
                "client_secret":app["client_info"]["client_secret"]
            }
    return "error"

if __name__ == "__main__":
    auth_hub_url = "http://10.43.204.227:8000"
    client_name = "EulerCopilot"
    client_url = "https://www.eulercopilot.local"
    redirect_urls = ["https://www.eulercopilot.local/api/auth/login"]
    user_token = get_user_token(auth_hub_url)
    response = register_app(auth_hub_url, user_token, client_name, client_url, redirect_urls)
    print(get_client_secret(auth_hub_url))
