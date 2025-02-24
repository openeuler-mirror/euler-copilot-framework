import asyncio
import copy
import json
import random
import time

import tiktoken
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from apps.common.config import config
from apps.dependency import (
    get_session,
    get_user,
    verify_csrf_token,
    verify_user,
)
from apps.entities.request_data import MockRequestData, RequestData
from apps.manager.flow import FlowManager
from apps.scheduler.pool.loader.flow import FlowLoader

router = APIRouter(
    prefix="/api",
    tags=["mock"],
)


def mock_data(appId="68dd3d90-6a97-4da0-aa62-d38a81c7d2f5", flowId="966c7964-e1c1-4bd8-9333-ed099cf25908", conversationId="eccb08c3-0621-4602-a4d2-4eaada892557", question="你好"):
    _encoder = tiktoken.get_encoding("cl100k_base")
    start_message = [{ # 任务流开始
                        "event": "flow.start",
                        "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                        "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                        "conversationId": conversationId,
                        "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                        "flow": {
                            "appId": appId,
                            "flowId": flowId,
                            "stepId": "start",
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
                            "time_cost": 0.5
                        }
                    },
                    {
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
                        "time_cost": 0.5
                    }
                },
                ]
    sample_input = { # 开始节点
                "event": "step.input",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "start",
                    "stepName": "开始",
                    "stepStatus": "running",
                },
                "content": {
                    "text":"测试输入"
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time_cost": 0.5,
                }
                }
    sample_output = { # 开始节点
                "event": "step.output",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13",
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "start",
                    "stepName": "开始",
                    "stepStatus": "success",
                },
                "content": {
                    "text":"测试输出"
                },
                "metadata": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time_cost": 0.5,
                }
                }
    mid_message = []
    flow = asyncio.run(FlowLoader.load(appId, flowId))
    now_flow_item = "start"
    start_time = time.time()
    last_item = ""
    mapp={}
    # print(json.dumps(flow))
    for step_id, step in flow.steps.items():
        mapp[step_id]= step.name, step.params
    while now_flow_item != "end":
        if last_item == now_flow_item:
            break
        #如果超过10s强制退出
        if time.time() - start_time > 10:
            break
        last_item = now_flow_item
        for edge in flow.edges:
            if edge.edge_from.split('.')[0] == now_flow_item:
                sample_input["flow"]["stepId"] = now_flow_item
                sample_input["flow"]["stepName"],sample_input["content"] = mapp[now_flow_item]
                sample_input["content"] = sample_input["content"]["input_parameters"] if now_flow_item != "start" else sample_input["content"]
                mid_message.append(copy.deepcopy(sample_input))
                sample_output["metadata"]["time_cost"] = random.uniform(0.5, 1.5)
                sample_output["flow"]["stepId"] = now_flow_item
                sample_output["flow"]["stepName"],sample_output["content"] = mapp[now_flow_item]
                sample_output["content"] = sample_output["content"]["output_parameters"] if now_flow_item != "start" else sample_output["content"]
                if sample_output["flow"]["stepName"] == "【RAG】知识库智能问答":
                    sample_output["content"] = call_rag()
                if sample_output["flow"]["stepName"] == "【LLM】模型问答":
                    sample_output["content"] = call_llm()
                mid_message.append(copy.deepcopy(sample_output))
                now_flow_item = edge.edge_to

    if now_flow_item == "end":
        sample_input["flow"]["stepId"] = now_flow_item
        sample_input["flow"]["stepName"] = "结束"
        mid_message.append(sample_input)
        sample_output["flow"]["stepId"] = now_flow_item
        sample_output["flow"]["stepName"] = "结束"
        sample_output["metadata"]["time_cost"] = random.uniform(0.5, 1.5)
        mid_message.append(sample_output)

    end_message =  [
            { # flow结束
                "event": "flow.stop",
                "id": "0f9d3e6b-7845-44ab-b247-35c522d38f13",
                "groupId":"8b9d3e6b-a892-4602-b247-35c522d38f13", 
                "conversationId": conversationId,
                "taskId": "eb717bc7-3435-4172-82d1-6b69e62f3fd6",
                "flow": {
                    "appId": appId,
                    "flowId":flowId,
                    "stepId": "end",
                    "stepName": "end",
                    "stepStatus": "success",
                },
                "content": {
                },
                "measure": {
                    "inputTokens": 200,
                    "outputTokens": 50,
                    "time_cost": 0.5
                }
            }]
    chat_message = [
        ]
    messages = []
    for message in start_message:
        messages.append(message)
    for message in mid_message:
        messages.append(message)
    for message in end_message:
        messages.append(message)
    for message in chat_message:
        messages.append(message)
    asyncio.run(FlowManager.updata_flow_debug_by_app_and_flow_id(appId,flowId,True))

    for message in messages:
        if message['event']=='step.output':
            t=message['metadata']['time_cost']
            time.sleep(t)
        elif message['event']=='text.add':
            t=random.uniform(0.15, 0.2)
            time.sleep(t)
        yield "data: " + json.dumps(message,ensure_ascii=False) + "\n\n"

async def call_rag():
    return "RAG"

async def call_llm():
    return "LLM"

@router.post("/mock/chat", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
async def chat(
    post_body: MockRequestData,
) -> StreamingResponse:
    """LLM流式对话接口"""
    res = mock_data(appId=post_body.app_id, conversationId=post_body.conversation_id, flowId=post_body.flow_id,question=post_body.question)
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )
