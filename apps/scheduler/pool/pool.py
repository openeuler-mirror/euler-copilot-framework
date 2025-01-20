"""配置池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

class Pool:
    """配置池"""

    @classmethod
    def load(cls) -> None:
        """加载配置池"""
        pass


    @classmethod
    def save(cls, *, is_deletion: bool = False) -> None:
        """保存配置池"""
        pass


    @classmethod
    def get_flow(cls, app_id: str, flow_id: str) -> None:
        """获取Flow"""
        pass
