"""Flow加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
from pathlib import Path

import yaml

from apps.common.config import config
from apps.entities.flow import Flow


class FlowLoader:
    """工作流加载器"""

    @classmethod
    def load(cls, app_id: str, flow_id: str) -> Flow:
        """从文件系统中加载【单个】工作流"""
        flow_path = Path(config["SERVICE_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"

        with flow_path.open(encoding="utf-8") as f:
            flow_yaml = yaml.safe_load(f)

        if "name" not in flow_yaml:
            err = f"工作流名称不能为空：{flow_path!s}"
            raise ValueError(err)

        if "::" in flow_yaml["id"]:
            err = f"工作流名称包含非法字符：{flow_path!s}"
            raise ValueError(err)

        try:
            # 检查Flow格式，并转换为Flow对象
            flow = Flow.model_validate(flow_yaml)
        except Exception as e:
            err = f"工作流格式错误：{e!s}; 文件路径：{flow_path!s}"
            raise ValueError(err) from e

        return flow


    @classmethod
    def save(cls, app_id: str, flow_id: str, flow: Flow) -> None:
        """保存工作流"""
        pass
