# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""枚举类型"""

from enum import Enum


class SlotType(str, Enum):
    """Slot类型"""

    FORMAT = "format"
    TYPE = "type"
    KEYWORD = "keyword"


class StepStatus(str, Enum):
    """步骤状态"""
    UNKNOWN = "unknown"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    PARAM = "param"
    CANCELLED = "cancelled"


class FlowStatus(str, Enum):
    """Flow状态"""

    UNKNOWN = "unknown"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class DocumentStatus(str, Enum):
    """文档状态"""

    USED = "used"
    UNUSED = "unused"
    PROCESSING = "processing"
    FAILED = "failed"


class EventType(str, Enum):
    """事件类型"""

    HEARTBEAT = "heartbeat"
    INIT = "init",
    TEXT_ADD = "text.add"
    GRAPH = "graph"
    DOCUMENT_ADD = "document.add"
    STEP_WAITING_FOR_START = "step.waiting_for_start"
    STEP_WAITING_FOR_PARAM = "step.waiting_for_param"
    FLOW_START = "flow.start"
    STEP_INPUT = "step.input"
    STEP_OUTPUT = "step.output"
    FLOW_STOP = "flow.stop"
    FLOW_FAILED = "flow.failed"
    FLOW_SUCCESS = "flow.success"
    FLOW_CANCELLED = "flow.cancelled"
    DONE = "done"


class CallType(str, Enum):
    """Call类型"""

    SYSTEM = "system"
    PYTHON = "python"


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


class SaveType(str, Enum):
    """检查类型"""

    APP = "app"
    SERVICE = "service"
    FLOW = "flow"


class PermissionType(str, Enum):
    """权限类型"""

    PROTECTED = "protected"
    PUBLIC = "public"
    PRIVATE = "private"


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


class CommentType(str, Enum):
    """点赞点踩类型"""

    LIKE = "liked"
    DISLIKE = "disliked"
    NONE = "none"


class AppType(str, Enum):
    """应用中心应用类型"""

    FLOW = "flow"
    AGENT = "agent"


class AppFilterType(str, Enum):
    """应用过滤类型"""

    ALL = "all"  # 所有已发布的应用
    USER = "user"  # 用户创建的应用
    FAVORITE = "favorite"  # 用户收藏的应用


class Role(str, Enum):
    """Message role类型"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AgentState(str, Enum):
    """Agent执行状态"""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
