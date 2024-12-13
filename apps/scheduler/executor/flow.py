# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
# Flow执行Executor，动态构建

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
import logging
import traceback

from apps.entities.plugin import Flow, Step
from apps.scheduler.core import Executor
from apps.scheduler.pool.pool import Pool
from apps.scheduler.utils import Summary, Evaluate, Reflect, BackProp

logger = logging.getLogger('gunicorn.error')


class FlowExecutorInput(BaseModel):
    name: str = Field(description="Flow的名称，格式为“插件名.工作流名”")
    question: str = Field(description="Flow所需要的输入")
    context: str = Field(description="Flow调用时的上下文信息")
    files: Optional[List[str]] = Field(description="适用于当前Flow调用的用户文件名")
    session_id: str = Field(description="当前的SessionID")


# 单个流的执行工具
class FlowExecuteExecutor(Executor):
    name: str
    description: str
    output: Dict[str, Any]

    question: str
    origin_question: str
    context: str
    error: str = "当前输入的效果不佳"

    flow: Flow | None
    files: List[str] | None
    session_id: str
    plugin: str
    retry: int = 3

    def __init__(self, params: Dict[str, Any]):
        params_obj = FlowExecutorInput(**params)
        # 指令与上下文
        self.question = params_obj.question
        self.origin_question = params_obj.question
        self.context = params_obj.context
        self.files = params_obj.files
        self.output = {}
        self.session_id = params_obj.session_id

        # 名字与插件
        self.plugin, self.name = params_obj.name.split(".")

        # 载入对应的Flow全部信息和Step信息
        flow, flow_data = Pool().get_flow(name=self.name, plugin_name=self.plugin)
        if flow is None or flow_data is None:
            raise ValueError("Flow不合法！")
        self.description = flow.description
        self.plugin = flow.plugin
        self.flow = flow_data

    # 运行流，返回各步骤经大模型总结后的内容，以及最后一步的工具原始输出
    async def run(self):
        current_step: Step | None = self.flow.steps.get("start", None)

        stop_flag = False
        while not stop_flag:
            # 当前步骤不存在，结束执行
            if current_step is None or current_step.call_type == "none":
                stop_flag = True
                continue

            # 当步骤为end，最后一步
            if current_step.name == "end":
                stop_flag = True
            call_data, call_cls = Pool().get_call(current_step.call_type, self.plugin)
            if call_data is None or call_cls is None:
                yield "data: 尝试执行工具{}时发生错误：找不到该工具。\n\n".format(current_step.call_type)
                stop_flag = True
                continue

            # 向Call传递已知参数，Call完成参数生成
            call_param = current_step.params
            call_param.update({
                "background": self.context,
                "files": self.files,
                "question": self.question,
                "plugin": self.plugin,
                "previous_data": self.output,
                "session_id": self.session_id
            })
            call_obj = call_cls(params=call_param)

            # 运行Call
            yield "data: 正在调用{}，请稍等...\n\n".format(current_step.call_type)
            try:
                result = await call_obj.call(fixed_params=call_param)
            except Exception as e:
                # 运行Call发生错误，
                logger.error(msg="尝试使用工具{}时发生错误：{}".format(current_step.call_type, traceback.format_exc()))
                self.error = str(e)
                yield "data: " + "尝试使用工具{}时发生错误，任务无法继续执行。\n\n".format(current_step.call_type)
                current_step = self.flow.on_error
                continue
            yield "data: 解析返回结果...\n\n"

            # 针对特殊Call进行特判
            if call_data.name == "choice":
                # Choice选择了Step，直接跳转，不保存信息
                current_step = self.flow.steps.get(result["next_step"], None)
                continue
            else:
                # 样例：{"type": "api", "data": {"message": "API返回值总结信息", "output": "API返回值原始数据（string）"}}
                self.output["type"] = current_step.call_type
                self.output["data"] = result

            # 需要进行打分的Call；执行Call完成后，进行打分
            if call_data.name in ["api",]:
                score, reason = await Evaluate().generate_evaluation(
                    user_question=self.question,
                    tool_output=result,
                    tool_description=self.description
                )

                # 效果低于预期时，进行重试
                if score < 2.0 and self.retry > 0:
                    reflection = await Reflect().generate_reflect(
                        self.question,
                        {
                            "name": current_step.call_type,
                            "description": call_data.description
                        },
                        call_input=call_param,
                        call_score_reason=reason
                    )

                    self.question = await BackProp().backprop(
                        user_input=self.question,
                        exception=self.error,
                        evaluation=reflection,
                        background=self.context
                    )

                    yield "data: 尝试执行{}时发生错误，正在尝试自我修正...\n\n".format(current_step.call_type)
                    self.retry -= 1
                    if self.retry == 0:
                        yield "data: 调用{}失败，将使用模型能力作答。\n\n".format(current_step.call_type)
                        self.question = self.origin_question
                        current_step = self.flow.on_error
                    continue
            yield "data: 生成摘要...\n\n"
            # 默认行为：达到效果，或者达到最高重试次数，完成调用
            self.context = await Summary().generate_summary(
                last_summary=self.context,
                qa_pair=[
                    self.origin_question,
                    result
                ],
                tool_info=[
                    current_step.call_type,
                    call_data.description,
                    json.dumps(call_param, ensure_ascii=False)
                ]
            )
            self.question = self.origin_question
            current_step = self.flow.steps.get(current_step.next, None)

        # 全部执行完成，输出最终结果
        flow_result = {
            "message": self.context,
            "output": self.output,
        }
        yield "final: " + json.dumps(flow_result, ensure_ascii=False)
