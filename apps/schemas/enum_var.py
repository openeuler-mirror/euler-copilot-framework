# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""枚举类型"""

from enum import Enum


class SlotType(str, Enum):
    """Slot类型"""

    FORMAT = "format"
    TYPE = "type"
    KEYWORD = "keyword"


class DocumentStatus(str, Enum):
    """文档状态"""

    USED = "used"
    UNUSED = "unused"
    PROCESSING = "processing"
    FAILED = "failed"


class EventType(str, Enum):
    """事件类型"""

    HEARTBEAT = "heartbeat"
    TEXT_ADD = "text.add"
    GRAPH = "graph"
    STEP_WAITING_FOR_START = "step.waiting_for_start"
    STEP_WAITING_FOR_PARAM = "step.waiting_for_param"
    EXECUTOR_START = "executor.start"
    STEP_INPUT = "step.input"
    STEP_OUTPUT = "step.output"
    STEP_END = "step.end"
    EXECUTOR_STOP = "executor.stop"
    DONE = "done"


class MetadataType(str, Enum):
    """元数据类型"""

    SERVICE = "service"
    APP = "app"
    MCP_SERVICE = "mcp_service"


class EdgeType(str, Enum):
    """
    边类型

    注：此处为临时定义，待扩展
    """

    NORMAL = "normal"
    LOOP = "loop"


class NodeType(str, Enum):
    """
    节点类型

    注：此处为临时定义，待扩展
    """

    START = "start"
    END = "end"
    NORMAL = "normal"
    CHOICE = "Choice"


class SearchType(str, Enum):
    """搜索类型"""

    ALL = "all"
    NAME = "name"
    DESCRIPTION = "description"
    AUTHOR = "author"


class HTTPMethod(str, Enum):
    """HTTP方法"""

    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"


class ContentType(str, Enum):
    """Content-Type"""

    JSON = "application/json"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    MULTIPART_FORM_DATA = "multipart/form-data"


class CallOutputType(str, Enum):
    """Call输出类型"""

    TEXT = "text"
    DATA = "data"


class SpecialCallType(str, Enum):
    """特殊Call类型"""

    EMPTY = "Empty"
    SUMMARY = "Summary"
    FACTS = "Facts"
    SLOT = "Slot"
    LLM = "LLM"
    START = "start"
    END = "end"
    CHOICE = "Choice"


class AppFilterType(str, Enum):
    """应用过滤类型"""

    ALL = "all"
    USER = "user"
    FAVORITE = "favorite"


class PromptType(str, Enum):
    """提示词类型枚举类"""
    PART = "part"
    CALL = "call"
    FUNC = "func"
    ROLE = "role"
