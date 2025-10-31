# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow相关的Mixin类"""

import logging
from copy import deepcopy

from jinja2.sandbox import SandboxedEnvironment

from apps.llm import json_generator
from apps.scheduler.pool.pool import pool
from apps.schemas.request_data import RequestData
from apps.schemas.scheduler import TopFlow
from apps.schemas.task import TaskData

from .prompt import FLOW_SELECT, FLOW_SELECT_FUNCTION

_logger = logging.getLogger(__name__)


class FlowMixin:
    """处理Flow相关的逻辑"""

    post_body: RequestData
    task: TaskData
    _env: SandboxedEnvironment

    async def get_top_flow(self) -> str:
        """获取Top1 Flow"""
        if not self.post_body.app or not self.post_body.app.app_id:
            err = "[Scheduler] 未选择应用"
            _logger.error(err)
            raise RuntimeError(err)

        flow_list = await pool.get_flow_metadata(self.post_body.app.app_id)
        if not flow_list:
            err = "[Scheduler] 未找到应用中合法的Flow"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[Scheduler] 选择应用 %s 最合适的Flow", self.post_body.app.app_id)
        choices = [{
            "name": flow.id,
            "description": f"{flow.name}, {flow.description}",
        } for flow in flow_list]

        template = self._env.from_string(FLOW_SELECT[self.task.runtime.language])
        prompt = template.render(
            template,
            question=self.post_body.question,
            choice_list=choices,
        )
        function = deepcopy(FLOW_SELECT_FUNCTION)
        function["parameters"]["properties"]["choice"]["enum"] = [choice["name"] for choice in choices]
        result_str = await json_generator.generate(
            function=function,
            conversation=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            language=self.task.runtime.language,
        )
        result = TopFlow.model_validate(result_str)
        return result.choice
