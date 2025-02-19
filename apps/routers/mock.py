from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
import json
import tiktoken
from apps.common.config import config
from apps.dependency import (
    get_session,
    get_user,
    verify_csrf_token,
    verify_user,
)
from apps.entities.request_data import MockRequestData

router = APIRouter(
    prefix="/api",
    tags=["mock"],
)


def mock_data(question):
    _encoder = tiktoken.get_encoding("cl100k_base")
    conversationId="eccb08c3-0621-4602-a4d2-4eaada892557"
    appId="68dd3d90-6a97-4da0-aa62-d38a81c7d2f5"
    flowId="966c7964-e1c1-4bd8-9333-ed099cf25908"
    messages =  [{
                    "event": "init",
                    "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                    "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                    "conversationId": conversationId,
                    "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                    "content": {
                        "feature": {
                            "enable_feedback": True,
                            "enable_regenerate": True,
                            "max_tokens": 2048,
                            "context_num": 2
                        }
                    },
                    "metadata": {
                        "input_tokens": 200,
                        "output_tokens": 50,
                        "time": 0.5
                    }
                },
            { # 任务流开始
                "event": "flow.start",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId": flowId,
                    "stepId": "eccb08c3-a892-4602-b247-35c522d38f13",
                    "stepStatus": "pending",
                },
                "content": {
                    "question": "查询所有主机的CVE信息",
                    "params": {
                        "cveId": "CVE-2021-44228",
                        "host": "192.168.10.1"
                    }
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5
                }
            },
            { # 开始节点
                "event": "step.input",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "node1",
                    "stepName": "开始",
                    "stepStatus": "running",
                },
                "content": {
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5,
                }
            },
            {
                "event": "step.output",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "node1",
                    "stepName": "开始",
                    "stepStatus": "success",
                },
                "content": {
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5,
                }
            },
            { # 【API】获取任务简介
                "event": "step.input",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "b7607efc-0dc7-4f7a-a2b2-dba60013b3b5",
                    "stepName": "【API】获取任务简介",
                    "stepStatus": "running",
                },
                "content": {
                    "full_url": "https://a-ops3.local/vulnerabilities/task/list/get",
                    "service_id": "aops-apollo",
                    "method": "post",
                    "input_data": {
                        "page": 1,
                        "page_size": 10,
                        "filter": {
                            "cluster_list": [],
                        },
                    },
                    "timeout": 300,
                    "output_key": [
                        {
                            "key": "data.result",
                            "path": "task_list",
                        },
                    ],
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5,
                }
            },
            { 
                "event": "step.output",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "b7607efc-0dc7-4f7a-a2b2-dba60013b3b5",
                    "stepName": "【API】获取任务简介",
                    "stepStatus": "success",
                },
                "content": {
                    "task_list":[
                        {
                            "task_id":"eb717bc7-3435-4172-82d1-6b12e62f3fd6",
                            "task_name":"A",
                            "task_type":"cve_scan",
                        },
                        {
                            "task_id":"eb717bc7-3435-4172-82d1-6b13e62f3fd6",
                            "task_name":"B",
                            "task_type":"cve_fix",
                        },
                    ]
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5,
                }
            },

            { # 【CHOICE】判断任务类型
                "event": "step.input",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "8841e328-da5b-45c7-8839-5b8054a92de7",
                    "stepName": "【CHOICE】判断任务类型",
                    "stepStatus": "running",
                },
                "content": {
                    "choices": [
                        {
                            "branchId": "is_scan",
                            "description": '任务类型为"CVE修复任务"',
                            "propose": '当值为cve_scan时，任务类型为"CVE修复任务"，选择此分支',
                            "variable_a": "{{input.task_list[0].task_type}}",
                        },
                        {
                            "branchId": "is_fix",
                            "description": '任务类型为"CVE修复任务"',
                            "propose": '当值为cve_fix时，任务类型为"CVE修复任务"，选择此分支',
                            "variable_a": "{{input.task_list[0].task_type}}",
                        },
                    ],
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5,
                }
            },
            { 
                "event": "step.output",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "8841e328-da5b-45c7-8839-5b8054a92de7",
                    "stepName": "【CHOICE】判断任务类型",
                    "stepStatus": "error",
                },
                "content": {
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5,
                }
            },

            { # flow结束
                "event": "flow.stop",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "8841e328-da5b-45c7-8839-5b8054a92de7",
                    "stepName": "【CHOICE】判断任务类型",
                    "stepStatus": "error",
                },
                "content": {
                },
                "measure": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5
                }
            },

            
            # 文字返回
            {
                "event": "text.add",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "content": {
                    "text": "<think>思考測試思考</think>"
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5
                }
            },

            {
                "event": "text.add",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "content": {
                    "text": "语句"
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5
                }
            },
            
            {
                "event": "text.add",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "content": {
                    "text": "语句"
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5
                }
            },

            {
                "event": "text.stop",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "content": {
                    "text": "[DONE]\n"
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time": 0.5
                }
            }
        ]
    
    import time
    import random
    for message in messages:
        if message['event']=='step.output':
            t=random.uniform(1, 1.5)
            time.sleep(t)
            message['time_cost']=t
        elif message['event']=='text.add':
            t=random.uniform(0.15, 0.2)
            time.sleep(t)
        yield "data: " + json.dumps(message,ensure_ascii=False) + "\n\n"


@router.post("/mock/chat", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
async def chat(
    post_body: MockRequestData,
) -> StreamingResponse:
    """LLM流式对话接口"""
    res = mock_data(post_body.question)
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )
