# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""生成大模型操作符配置文件"""

import base64
import os

llm_provider_dict={
    "baichuan":{
        "provider":"baichuan",
        "url":"https://api.baichuan-ai.com/v1",
        "description":"百川大模型平台",
        "icon":"",
    },
    "siliconflow":{
        "provider":"siliconflow",
        "url":"https://api.siliconflow.cn/v1",
        "description":"硅基流动",
        "icon":"",
    },
    "modelscope":{
        "provider":"modelscope",
        "url":None,
        "description":"基于魔塔部署的本地大模型服务",
        "icon":"",
    },
    "ollama":{
        "provider":"ollama",
        "url":None,
        "description":"基于Ollama部署的本地大模型服务",
        "icon":"",
    },
    "openai":{
        "provider":"openai",
        "url":"https://api.openai.com/v1",
        "description":"OpenAI大模型平台",
        "icon":"",
    },
    "qwen":{
        "provider":"qwen",
        "url":"https://dashscope.aliyuncs.com/compatible-mode/v1",
        "description":"阿里百炼大模型平台",
        "icon":"",
    },
    "spark":{
        "provider":"spark",
        "url":"https://spark-api-open.xf-yun.com/v1",
        "description":"讯飞星火大模型平台",
        "icon":"",
    },
    "vllm":{
        "provider":"vllm",
        "url":None,
        "description":"基于VLLM部署的本地大模型服务",
        "icon":"",
    },
    "mindie":{
        "provider":"mindie",
        "url":None,
        "description":"基于MindIE部署的本地大模型服务",
        "icon":"",
    },
    "wenxin":{
        "provider":"wenxin",
        "url":"https://qianfan.baidubce.com/v2",
        "description":"百度文心大模型平台",
        "icon":"",
    },
}
icon_path="./apps/templates/llm_provider_icon"
icon_file_name_list=os.listdir(icon_path)
for file_name in icon_file_name_list:
    provider_name=file_name.split('.')[0]
    file_path=os.path.join(icon_path, file_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        svg_content = file.read()
    svg_bytes = svg_content.encode('utf-8')
    base64_bytes = base64.b64encode(svg_bytes)
    base64_string = base64_bytes.decode('utf-8')
    for provider in llm_provider_dict.keys():
        if provider_name in provider:
            llm_provider_dict[provider]['icon'] = f"data:image/svg+xml;base64,{base64_string}"
            break
