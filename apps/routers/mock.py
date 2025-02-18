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
    messages =  [
            {
                "event": "node_finish_work",
                "node_id": "abc",
                "status": "pending",
                "input_parameters": {},
                "output_parameters": {},
                "time_cost": 0
            },
            {
                "event": "node_start_work",
                "node_id": "",
                "status": "pending"
            },
           {
                "event": "node_finish_work",
                "node_id": "",
                "status": "success",
                "input_parameters": {
                    "page": 1,
                    "page_size": 10,
                    "sort": "create_time",
                    "direction": "desc",
                    "filter": {
                        "cluster_list": [],
                        "task_type": ["cve_scan", "cve_fix", "repo_set", "hotpatch_remove"]
                    }
                },
                "output_parameters": {
                    "task_list": [
                        {
                            "task_id": "1",
                            "task_name": "扫描主机192.168.10.133的漏洞",
                            "task_type": "cve_scan"
                        },
                        {
                            "task_id": "2",
                            "task_name": "修复主机192.168.10.42的CVE-2024-1086",
                            "task_type": "cve_fix"
                        }
                    ]
                },
                "time_cost": 1.0
            },
            {
                "event": "node_start_work",
                "node_id": "",
                "status": "pending"
            },
            {
                "event": "node_finish_work",
                "node_id": "",
                "status": "success",
                "input_parameters": {
                    "input": {
                        "content"
                        "task_list": [
                            {
                                "task_id": "1",
                                "task_name": "扫描主机192.168.10.133的漏洞",
                                "task_type": "cve_scan"
                            },
                            {
                                "task_id": "2",
                                "task_name": "修复主机192.168.10.42的CVE-2024-1086",
                                "task_type": "cve_fix"
                            }
                        ]
                    }
                },
                "output_parameters": {},
                "time_cost": 1.0
            },
            {
                "event": "node_start_work",
                "node_id": "",
                "status": "pending"
            },
            {
                "event": "node_finish_work",
                "node_id": "",
                "status": "success",
                "input_parameters": {
                    "page": 1,
                    "page_size": 10,
                    "sort": "create_time",
                    "direction": "desc",
                    "filter": {
                        "cluster_list": [],
                        "task_type": ["cve_scan", "cve_fix", "repo_set", "hotpatch_remove"]
                    }
                },
                "output_parameters": {
                    "task_list": [
                        {
                            "task_id": "1",
                            "task_name": "扫描主机192.168.10.133的漏洞",
                            "task_type": "cve_scan"
                        },
                        {
                            "task_id": "2",
                            "task_name": "修复主机192.168.10.42的CVE-2024-1086",
                            "task_type": "cve_fix"
                        }
                    ]
                },
                "time_cost": 1.0
            },
            {
                "event": "node_start_work",
                "node_id": "",
                "status": "pending"
            },
            {
                "event": "node_finish_work",
                "node_id": "",
                "status": "success",
                "input_parameters": {
                    "input": {
                        "task_id": "d38fb273-42bf-4281-906e-26370f3544a6"
                    }
                },
                "output_parameters": {
                    "result": {
                        "last_execute_time": 1739847731,
                        "task_type": "cve_fix",
                        "task_result": [
                            {
                                "timed": False,
                                "rpms": [
                                    {
                                        "avaliable_rpm": "kernel",
                                        "result": "success"
                                    }
                                ]
                            }
                        ]
                    }
                },
                "time_cost": 1.0
            },
            {
                "event": "node_start_work",
                "node_id": "",
                "status": "pending"
            },
            {
                "event": "node_finish_work",
                "node_id": "",
                "status": "success",
                "input_parameters": {
                    "task_id": "8e29da5d-7de2-42be-a1f7-b261f7eb32cf"
                },
                "output_parameters": {
                    "status_code": 200,
                    "data": {
                        "result": {
                            "last_execute_time": 1739847731,
                            "task_type": "cve_scan",
                            "task_result": [
                                {
                                    "timed": False,
                                    "cve_list": [
                                        {
                                            "cve_id": "CVE-2024-1086",
                                            "cve_description": "CVE-2024-1086, a use-after-free vulnerability in the Linux kernel's netfilter, was disclosed on January 31, 2024 and assigned a CVSS of 7.8 (High). If successfully exploited, it could allow threat actors to achieve local privilege escalation.",
                                            "rpms": [
                                                "kernel"
                                            ],
                                            "severity": "High",
                                            "cvss_score": 7.8
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                },
                "time_cost": 1.0
            },
            {
                "event": "node_start_work",
                "node_id": "",
                "status": "pending"
            },
            {
                "event": "node_finish_work",
                "node_id": "",
                "status": "",
                "input_parameters": {
                    "input": {}
                    },
                "output_parameters": {
                "message": "streamanswer"
                },
                "time_cost": 1.0
            },
            {
                "event": "node_finish_work",
                "node_id": "abc",
                "status": "success",
                "input_parameters": {},
                "output_parameters": {},
                "time_cost": 0
            },
           {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 1}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 2}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 3}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 4}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 5}
            ,{"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 6}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 7}
            ,
            {"event": "text", "content": "执行", "input_tokens": len(_encoder.encode(question)), "output_tokens": 8}
            ,
            {"event": "text", "content": "报告", "input_tokens": len(_encoder.encode(question)), "output_tokens": 10}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 11}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 12}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 13}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 14}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 15}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 16}
            ,
            {"event": "text", "content": "以下", "input_tokens": len(_encoder.encode(question)), "output_tokens": 17}
            ,
            {"event": "text", "content": "是", "input_tokens": len(_encoder.encode(question)), "output_tokens": 18}
            ,
            {"event": "text", "content": "本次", "input_tokens": len(_encoder.encode(question)), "output_tokens": 20}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 21}
            ,
            {"event": "text", "content": "的", "input_tokens": len(_encoder.encode(question)), "output_tokens": 22}
            ,
            {"event": "text", "content": "执行", "input_tokens": len(_encoder.encode(question)), "output_tokens": 23}
            ,
            {"event": "text", "content": "信息", "input_tokens": len(_encoder.encode(question)), "output_tokens": 24}
            ,
            {"event": "text", "content": "详情", "input_tokens": len(_encoder.encode(question)), "output_tokens": 25}
            ,
            {"event": "text", "content": "：", "input_tokens": len(_encoder.encode(question)), "output_tokens": 26}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 27}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 28}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 29}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 30}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 31}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 32}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 33}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 34}
            ,
            {"event": "text", "content": "名称", "input_tokens": len(_encoder.encode(question)), "output_tokens": 35}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 36}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 37}
            ,
            {"event": "text", "content": "类型", "input_tokens": len(_encoder.encode(question)), "output_tokens": 38}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 39}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 40}
            ,
            {"event": "text", "content": "执行", "input_tokens": len(_encoder.encode(question)), "output_tokens": 41}
            ,
            {"event": "text", "content": "时间", "input_tokens": len(_encoder.encode(question)), "output_tokens": 42}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 43}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 44}
            ,
            {"event": "text", "content": "执行", "input_tokens": len(_encoder.encode(question)), "output_tokens": 45}
            ,
            {"event": "text", "content": "结果", "input_tokens": len(_encoder.encode(question)), "output_tokens": 46}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 47}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 48}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 49}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 50}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 51}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 52}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 53}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 54}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 55}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 56}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 57}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 58}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 59}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 60}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 61}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 62}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 63}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 64}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 65}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 66}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 67}
            ,
            {"event": "text", "content": "d38fb273", "input_tokens": len(_encoder.encode(question)), "output_tokens": 71}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 72}
            ,
            {"event": "text", "content": "42bf", "input_tokens": len(_encoder.encode(question)), "output_tokens": 74}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 75}
            ,
            {"event": "text", "content": "4281", "input_tokens": len(_encoder.encode(question)), "output_tokens": 77}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 78}
            ,
            {"event": "text", "content": "906e", "input_tokens": len(_encoder.encode(question)), "output_tokens": 80}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 81}
            ,
            {"event": "text", "content": "26370f3544a6", "input_tokens": len(_encoder.encode(question)), "output_tokens": 88}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 89}
            ,
            {"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 90}
            ,
            {"event": "text", "content": "修复", "input_tokens": len(_encoder.encode(question)), "output_tokens": 92}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 93}
            ,
            {"event": "text", "content": "2025", "input_tokens": len(_encoder.encode(question)), "output_tokens": 95}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 96}
            ,
            {"event": "text", "content": "02", "input_tokens": len(_encoder.encode(question)), "output_tokens": 97}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 98}
            ,
            {"event": "text", "content": "18", "input_tokens": len(_encoder.encode(question)), "output_tokens": 99}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 100}
            ,
            {"event": "text", "content": "10", "input_tokens": len(_encoder.encode(question)), "output_tokens": 101}
            ,
            {"event": "text", "content": ":", "input_tokens": len(_encoder.encode(question)), "output_tokens": 102}
            ,
            {"event": "text", "content": "32", "input_tokens": len(_encoder.encode(question)), "output_tokens": 103}
            ,
            {"event": "text", "content": ":", "input_tokens": len(_encoder.encode(question)), "output_tokens": 104}
            ,
            {"event": "text", "content": "00", "input_tokens": len(_encoder.encode(question)), "output_tokens": 105}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 106}
            ,
            {"event": "text", "content": "执行", "input_tokens": len(_encoder.encode(question)), "output_tokens": 107}
            ,
            {"event": "text", "content": "成功", "input_tokens": len(_encoder.encode(question)), "output_tokens": 108}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 109}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 110}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 111}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 112}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 113}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 114}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 115}
            ,
            {"event": "text", "content": "根据", "input_tokens": len(_encoder.encode(question)), "output_tokens": 118}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 119}
            ,
            {"event": "text", "content": "信息", "input_tokens": len(_encoder.encode(question)), "output_tokens": 120}
            ,
            {"event": "text", "content": "，", "input_tokens": len(_encoder.encode(question)), "output_tokens": 121}
            ,
            {"event": "text", "content": "本次", "input_tokens": len(_encoder.encode(question)), "output_tokens": 123}
            ,
            {"event": "text", "content": "任务", "input_tokens": len(_encoder.encode(question)), "output_tokens": 124}
            ,
            {"event": "text", "content": "共", "input_tokens": len(_encoder.encode(question)), "output_tokens": 125}
            ,
            {"event": "text", "content": "修复", "input_tokens": len(_encoder.encode(question)), "output_tokens": 127}
            ,
            {"event": "text", "content": "了", "input_tokens": len(_encoder.encode(question)), "output_tokens": 128}
            ,
            {"event": "text", "content": "1", "input_tokens": len(_encoder.encode(question)), "output_tokens": 129}
            ,
            {"event": "text", "content": "个", "input_tokens": len(_encoder.encode(question)), "output_tokens": 130}
            ,
            {"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 131}
            ,
            {"event": "text", "content": "漏洞", "input_tokens": len(_encoder.encode(question)), "output_tokens": 135}
            ,
            {"event": "text", "content": "，", "input_tokens": len(_encoder.encode(question)), "output_tokens": 136}
            ,
            {"event": "text", "content": "分别", "input_tokens": len(_encoder.encode(question)), "output_tokens": 138}
            ,
            {"event": "text", "content": "是", "input_tokens": len(_encoder.encode(question)), "output_tokens": 139}
            ,
            {"event": "text", "content": "：", "input_tokens": len(_encoder.encode(question)), "output_tokens": 140}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 141}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 142}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 143}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 144}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 145}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 146}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 147}
            ,
            {"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 148}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 149}
            ,
            {"event": "text", "content": "ID", "input_tokens": len(_encoder.encode(question)), "output_tokens": 150}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 151}
            ,
            {"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 152}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 153}
            ,
            {"event": "text", "content": "描述", "input_tokens": len(_encoder.encode(question)), "output_tokens": 154}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 155}
            ,
            {"event": "text", "content": "修复", "input_tokens": len(_encoder.encode(question)), "output_tokens": 157}
            ,
            {"event": "text", "content": "结果", "input_tokens": len(_encoder.encode(question)), "output_tokens": 158}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 159}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 160}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 161}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 162}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 163}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 164}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 165}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 166}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 167}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 168}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 169}
            ,
            {"event": "text", "content": "---", "input_tokens": len(_encoder.encode(question)), "output_tokens": 170}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 171}
            ,
            {"event": "text", "content": "\n", "input_tokens": len(_encoder.encode(question)), "output_tokens": 172}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 173}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 174}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 175}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 176}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 177}
            ,
            {"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 178}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 179}
            ,
            {"event": "text", "content": "2024", "input_tokens": len(_encoder.encode(question)), "output_tokens": 181}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 182}
            ,
            {"event": "text", "content": "1086", "input_tokens": len(_encoder.encode(question)), "output_tokens": 184}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 185}
            ,
            {"event": "text", "content": "CVE", "input_tokens": len(_encoder.encode(question)), "output_tokens": 186}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 187}
            ,
            {"event": "text", "content": "2024", "input_tokens": len(_encoder.encode(question)), "output_tokens": 189}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 190}
            ,
            {"event": "text", "content": "1086", "input_tokens": len(_encoder.encode(question)), "output_tokens": 192}
            ,
            {"event": "text", "content": ",", "input_tokens": len(_encoder.encode(question)), "output_tokens": 193}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 194}
            ,
            {"event": "text", "content": "a", "input_tokens": len(_encoder.encode(question)), "output_tokens": 195}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 196}
            ,
            {"event": "text", "content": "use", "input_tokens": len(_encoder.encode(question)), "output_tokens": 197}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 198}
            ,
            {"event": "text", "content": "after", "input_tokens": len(_encoder.encode(question)), "output_tokens": 199}
            ,
            {"event": "text", "content": "-", "input_tokens": len(_encoder.encode(question)), "output_tokens": 200}
            ,
            {"event": "text", "content": "free", "input_tokens": len(_encoder.encode(question)), "output_tokens": 201}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 202}
            ,
            {"event": "text", "content": "vulnerability", "input_tokens": len(_encoder.encode(question)), "output_tokens": 205}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 206}
            ,
            {"event": "text", "content": "in", "input_tokens": len(_encoder.encode(question)), "output_tokens": 207}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 208}
            ,
            {"event": "text", "content": "the", "input_tokens": len(_encoder.encode(question)), "output_tokens": 209}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 210}
            ,
            {"event": "text", "content": "Linux", "input_tokens": len(_encoder.encode(question)), "output_tokens": 211}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 212}
            ,
            {"event": "text", "content": "kernel", "input_tokens": len(_encoder.encode(question)), "output_tokens": 213}
            ,
            {"event": "text", "content": "'", "input_tokens": len(_encoder.encode(question)), "output_tokens": 214}
            ,
            {"event": "text", "content": "s", "input_tokens": len(_encoder.encode(question)), "output_tokens": 215}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 216}
            ,
            {"event": "text", "content": "netfilter", "input_tokens": len(_encoder.encode(question)), "output_tokens": 218}
            ,
            {"event": "text", "content": ",", "input_tokens": len(_encoder.encode(question)), "output_tokens": 219}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 220}
            ,
            {"event": "text", "content": "was", "input_tokens": len(_encoder.encode(question)), "output_tokens": 221}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 222}
            ,
            {"event": "text", "content": "disclosed", "input_tokens": len(_encoder.encode(question)), "output_tokens": 224}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 225}
            ,
            {"event": "text", "content": "on", "input_tokens": len(_encoder.encode(question)), "output_tokens": 226}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 227}
            ,
            {"event": "text", "content": "January", "input_tokens": len(_encoder.encode(question)), "output_tokens": 228}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 229}
            ,
            {"event": "text", "content": "31", "input_tokens": len(_encoder.encode(question)), "output_tokens": 230}
            ,
            {"event": "text", "content": ",", "input_tokens": len(_encoder.encode(question)), "output_tokens": 231}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 232}
            ,
            {"event": "text", "content": "2024", "input_tokens": len(_encoder.encode(question)), "output_tokens": 234}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 235}
            ,
            {"event": "text", "content": "and", "input_tokens": len(_encoder.encode(question)), "output_tokens": 236}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 237}
            ,
            {"event": "text", "content": "assigned", "input_tokens": len(_encoder.encode(question)), "output_tokens": 238}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 239}
            ,
            {"event": "text", "content": "a", "input_tokens": len(_encoder.encode(question)), "output_tokens": 240}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 241}
            ,
            {"event": "text", "content": "CVSS", "input_tokens": len(_encoder.encode(question)), "output_tokens": 243}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 244}
            ,
            {"event": "text", "content": "of", "input_tokens": len(_encoder.encode(question)), "output_tokens": 245}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 246}
            ,
            {"event": "text", "content": "7.8", "input_tokens": len(_encoder.encode(question)), "output_tokens": 249}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 250}
            ,
            {"event": "text", "content": "(", "input_tokens": len(_encoder.encode(question)), "output_tokens": 251}
            ,
            {"event": "text", "content": "High", "input_tokens": len(_encoder.encode(question)), "output_tokens": 252}
            ,
            {"event": "text", "content": ")", "input_tokens": len(_encoder.encode(question)), "output_tokens": 253}
            ,
            {"event": "text", "content": ".", "input_tokens": len(_encoder.encode(question)), "output_tokens": 254}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 255}
            ,
            {"event": "text", "content": "If", "input_tokens": len(_encoder.encode(question)), "output_tokens": 256}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 257}
            ,
            {"event": "text", "content": "successfully", "input_tokens": len(_encoder.encode(question)), "output_tokens": 258}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 259}
            ,
            {"event": "text", "content": "exploited", "input_tokens": len(_encoder.encode(question)), "output_tokens": 261}
            ,
            {"event": "text", "content": ",", "input_tokens": len(_encoder.encode(question)), "output_tokens": 262}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 263}
            ,
            {"event": "text", "content": "it", "input_tokens": len(_encoder.encode(question)), "output_tokens": 264}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 265}
            ,
            {"event": "text", "content": "could", "input_tokens": len(_encoder.encode(question)), "output_tokens": 266}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 267}
            ,
            {"event": "text", "content": "allow", "input_tokens": len(_encoder.encode(question)), "output_tokens": 268}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 269}
            ,
            {"event": "text", "content": "threat", "input_tokens": len(_encoder.encode(question)), "output_tokens": 270}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 271}
            ,
            {"event": "text", "content": "actors", "input_tokens": len(_encoder.encode(question)), "output_tokens": 272}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 273}
            ,
            {"event": "text", "content": "to", "input_tokens": len(_encoder.encode(question)), "output_tokens": 274}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 275}
            ,
            {"event": "text", "content": "achieve", "input_tokens": len(_encoder.encode(question)), "output_tokens": 277}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 278}
            ,
            {"event": "text", "content": "local", "input_tokens": len(_encoder.encode(question)), "output_tokens": 279}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 280}
            ,
            {"event": "text", "content": "privilege", "input_tokens": len(_encoder.encode(question)), "output_tokens": 282}
            ,
            {"event": "text", "content": " ", "input_tokens": len(_encoder.encode(question)), "output_tokens": 283}
            ,
            {"event": "text", "content": "escalation", "input_tokens": len(_encoder.encode(question)), "output_tokens": 285}
            ,
            {"event": "text", "content": ".", "input_tokens": len(_encoder.encode(question)), "output_tokens": 286}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 287}
            ,
            {"event": "text", "content": "执行", "input_tokens": len(_encoder.encode(question)), "output_tokens": 288}
            ,
            {"event": "text", "content": "成功", "input_tokens": len(_encoder.encode(question)), "output_tokens": 289}
            ,
            {"event": "text", "content": "|", "input_tokens": len(_encoder.encode(question)), "output_tokens": 290}
        ]
    import time
    import random
    for message in messages:
        if message['event']=='node_finish_work':
            t=random.uniform(1, 1.5)
            time.sleep(t)
            message['time_cost']=t
        elif message['event']=='text':
            t=random.uniform(0.15, 0.2)
            time.sleep(t)
        yield "data: " + json.dumps(message,ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


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
