"""资源池，包含语义接口、应用等的载入和保存

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

class Pool:
    """资源池"""

    @classmethod
    def load(cls) -> None:
        """加载全部文件系统内的资源"""
        pass


    @classmethod
    def save(cls, *, is_deletion: bool = False) -> None:
        """保存【单个】资源"""
        pass


    @classmethod
    def get_flow(cls, app_id: str, flow_id: str) -> None:
        """获取【单个】Flow完整数据"""
        pass
