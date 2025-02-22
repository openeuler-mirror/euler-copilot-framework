"""样例工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""
# 这里应当导入所有工具类型
from .user_tool import UserTool

# 【必填】使用__all__暴露所有Call Class
__all__ = [
    "UserTool",
]

# 【必填】这个工具关联的服务
service = "test_service"
