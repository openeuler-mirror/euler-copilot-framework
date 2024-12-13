# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from __future__ import annotations

import json
import os
from typing import Dict, Any, List

from apps.scheduler.call.core import CoreCall, CallParams
from apps.scheduler.encoder import JSONSerializer
from apps.scheduler.call.render.style import RenderStyle


class Render(CoreCall):
    """
    Render Call，用于将SQL Tool查询出的数据转换为图表
    """

    name = "render"
    description = "渲染图表工具，可将给定的数据绘制为图表。"
    params_obj: CallParams

    option_template: Dict[str, Any]

    def __init__(self, params: Dict[str, Any]):
        """
        初始化Render Call，校验参数，读取option模板
        :param params: Render Call参数
        """
        self.params_obj = CallParams(**params)

        option_location = os.path.join(os.path.dirname(os.path.realpath(__file__)), "option.json")
        self.option_template = json.load(open(option_location, "r", encoding="utf-8"))

    async def call(self, fixed_params: Dict[str, Any] | None = None):
        if fixed_params is not None:
            self.params_obj = CallParams(**fixed_params)

        # 检测前一个工具是否为SQL
        data = self.params_obj.previous_data
        if data["type"] != "sql":
            return {
                "output": "",
                "message": "图表生成失败！Render必须在SQL后调用！"
            }
        data = json.loads(data["data"]["output"])

        # 判断数据格式是否满足要求
        # 样例：[{'openeuler_version': 'openEuler-22.03-LTS-SP2', '软件数量': 10}]
        malformed = True
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                malformed = False

        # 将执行SQL工具查询到的数据转换为特定格式
        if malformed:
            return {
                "output": "",
                "message": "SQL未查询到数据，或数据格式错误，无法生成图表！"
            }

        # 对少量数据进行处理
        column_num = len(data[0]) - 1
        if column_num == 0:
            data = Render._separate_key_value(data)
            column_num = 1

        # 该格式满足ECharts DataSource要求，与option模板进行拼接
        self.option_template["dataset"]["source"] = data

        llm_output = await RenderStyle().generate_option(self.params_obj.question)
        add_style = ""
        if "add" in llm_output:
            add_style = llm_output["add"]

        self._parse_options(column_num, llm_output["style"], add_style, llm_output["scale"])

        return {
            "output": json.dumps(self.option_template, cls=JSONSerializer),
            "message": "图表生成成功！图表将使用外置工具进行展示。"
        }

    @staticmethod
    def _separate_key_value(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        若数据只有一组（例如：{"aaa": "bbb"}），则分离键值对。
        样例：{"type": "aaa", "value": "bbb"}
        :param data: 待分离的数据
        :return: 分离后的数据
        """
        result = []
        for item in data:
            for key, val in item.items():
                result.append({"type": key, "value": val})
        return result

    def _parse_options(self, column_num: int, graph_style: str, additional_style: str, scale_style: str):
        series_template = {}

        if graph_style == "line":
            series_template["type"] = "line"
        elif graph_style == "scatter":
            series_template["type"] = "scatter"
        elif graph_style == "pie":
            column_num = 1
            series_template["type"] = "pie"
            if additional_style == "ring":
                series_template["radius"] = ["40%", "70%"]
        else:
            series_template["type"] = "bar"
            if additional_style == "stacked":
                series_template["stack"] = "total"

        if scale_style == "log":
            self.option_template["yAxis"]["type"] = "log"

        for i in range(column_num):
            self.option_template["series"].append(series_template)
