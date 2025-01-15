"""Call: Render，用于将SQL Tool查询出的数据转换为图表

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import json
from pathlib import Path
from typing import Any

from apps.entities.plugin import CallError, CallResult, SysCallVars
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.render.style import RenderStyle


class Render(CoreCall):
    """Render Call，用于将SQL Tool查询出的数据转换为图表"""

    name: str = "render"
    description: str = "渲染图表工具，可将给定的数据绘制为图表。"


    async def init(self, syscall_vars: SysCallVars, **_kwargs) -> None:  # noqa: ANN003
        """初始化Render Call，校验参数，读取option模板

        :param syscall_vars: Render Call参数
        """
        await super().init(syscall_vars, **_kwargs)

        try:
            option_location = Path(__file__).parent / "option.json"
            with Path(option_location).open(encoding="utf-8") as f:
                self._option_template = json.load(f)
        except Exception as e:
            raise CallError(message=f"图表模板读取失败：{e!s}", data={}) from e


    async def call(self, _slot_data: dict[str, Any]) -> CallResult:
        """运行Render Call"""
        # 检测前一个工具是否为SQL
        data = CallResult(**self._syscall_vars.history[-1].output_data).output
        if data["type"] != "sql" or "dataset" not in data:
            raise CallError(
                message="图表生成失败！Render必须在SQL后调用！",
                data={},
            )
        data = json.loads(data["dataset"])

        # 判断数据格式是否满足要求
        # 样例：[{'openeuler_version': 'openEuler-22.03-LTS-SP2', '软件数量': 10}]
        malformed = True
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            malformed = False

        # 将执行SQL工具查询到的数据转换为特定格式
        if malformed:
            raise CallError(
                message="SQL未查询到数据，或数据格式错误，无法生成图表！",
                data={"data": data},
            )

        # 对少量数据进行处理
        column_num = len(data[0]) - 1
        if column_num == 0:
            data = Render._separate_key_value(data)
            column_num = 1

        # 该格式满足ECharts DataSource要求，与option模板进行拼接
        self._option_template["dataset"]["source"] = data

        try:
            llm_output = await RenderStyle().generate(self._syscall_vars.task_id, question=self._syscall_vars.question)
            add_style = llm_output.get("additional_style", "")
            self._parse_options(column_num, llm_output["chart_type"], add_style, llm_output["scale_type"])
        except Exception as e:
            raise CallError(message=f"图表生成失败：{e!s}", data={"data": data}) from e

        return CallResult(
            output=self._option_template,
            output_schema={
                "type": "object",
                "description": "ECharts图表配置",
                "properties": {
                    "tooltip": {
                        "type": "object",
                        "description": "ECharts图表的提示框配置",
                    },
                    "legend": {
                        "type": "object",
                        "description": "ECharts图表的图例配置",
                    },
                    "dataset": {
                        "type": "object",
                        "description": "ECharts图表的数据集配置",
                    },
                    "xAxis": {
                        "type": "object",
                        "description": "ECharts图表的X轴配置",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "ECharts图表的X轴类型",
                                "default": "category",
                            },
                            "axisTick": {
                                "type": "object",
                                "description": "ECharts图表的X轴刻度配置",
                            },
                        },
                    },
                    "yAxis": {
                        "type": "object",
                        "description": "ECharts图表的Y轴配置",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "ECharts图表的Y轴类型",
                                "default": "value",
                            },
                        },
                    },
                    "series": {
                        "type": "array",
                        "description": "ECharts图表的数据列配置",
                    },
                },
            },
            message="图表生成成功！图表将使用外置工具进行展示。",
        )

    @staticmethod
    def _separate_key_value(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """若数据只有一组（例如：{"aaa": "bbb"}），则分离键值对。

        样例：{"type": "aaa", "value": "bbb"}

        :param data: 待分离的数据
        :return: 分离后的数据
        """
        result = []
        for item in data:
            for key, val in item.items():
                result.append({"type": key, "value": val})
        return result

    def _parse_options(self, column_num: int, chart_style: str, additional_style: str, scale_style: str) -> None:
        """解析LLM做出的图表样式选择"""
        series_template = {}

        if chart_style == "line":
            series_template["type"] = "line"
        elif chart_style == "scatter":
            series_template["type"] = "scatter"
        elif chart_style == "pie":
            column_num = 1
            series_template["type"] = "pie"
            if additional_style == "ring":
                series_template["radius"] = ["40%", "70%"]
        else:
            series_template["type"] = "bar"
            if additional_style == "stacked":
                series_template["stack"] = "total"

        if scale_style == "log":
            self._option_template["yAxis"]["type"] = "log"

        for _ in range(column_num):
            self._option_template["series"].append(series_template)
