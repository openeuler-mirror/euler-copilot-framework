"""Flow加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
import yaml
from anyio import Path

from apps.common.config import config
from apps.entities.flow import Flow


class FlowLoader:
    """工作流加载器"""

    @classmethod
    async def load(cls, app_id: str, flow_id: str) -> Flow:
        """从文件系统中加载【单个】工作流"""
        flow_path = Path(config["SEMANTICS_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"

        f = await flow_path.open(encoding="utf-8")
        flow_yaml = yaml.safe_load(await f.read())
        await f.aclose()

        flow_yaml["id"] = flow_id
        try:
            # 检查Flow格式，并转换为Flow对象
            flow = Flow.model_validate(flow_yaml)
        except Exception as e:
            err = f"工作流格式错误：{e!s}; 文件路径：{flow_path!s}"
            raise ValueError(err) from e

        return flow


    @classmethod
    async def save(cls, app_id: str, flow_id: str, flow: Flow) -> None:
        """保存工作流"""
        file = Path(config["SEMANTICS_DIR"]) / "app" / app_id / "flow" / f"{flow_id}.yaml"

        file_handler = await file.open(mode="w", encoding="utf-8")
        yaml.dump(flow.model_dump(), file_handler)
        await file_handler.aclose()
