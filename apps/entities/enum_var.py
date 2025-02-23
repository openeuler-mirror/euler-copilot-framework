"""枚举类型

Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.
"""

from enum import Enum


class SlotType(str, Enum):
    """Slot类型"""

    FORMAT = "format"
    TYPE = "type"
    KEYWORD = "keyword"


class StepStatus(str, Enum):
    """步骤状态"""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    PARAM = "param"


class DocumentStatus(str, Enum):
    """文档状态"""

    USED = "used"
    UNUSED = "unused"
    PROCESSING = "processing"
    FAILED = "failed"


class FlowOutputType(str, Enum):
    """Flow输出类型"""

    CODE = "code"
    CHART = "chart"
    URL = "url"
    SCHEMA = "schema"
    NONE = "none"


class EventType(str, Enum):
    """事件类型"""

    HEARTBEAT = "heartbeat"
    INIT = "init"
    TEXT_ADD = "text.add"
    DOCUMENT_ADD = "document.add"
    SUGGEST = "suggest"
    FLOW_START = "flow.start"
    STEP_INPUT = "step.input"
    STEP_OUTPUT = "step.output"
    FLOW_STOP = "flow.stop"
    DONE = "done"


class CallType(str, Enum):
    """Call类型"""

    SYSTEM = "system"
    PYTHON = "python"


class MetadataType(str, Enum):
    """元数据类型"""

    SERVICE = "service"
    APP = "app"


class EdgeType(str, Enum):
    """边类型

    注：此处为临时定义，待扩展
    """

    NORMAL = "normal"
    LOOP = "loop"


class NodeType(str, Enum):
    """节点类型

    注：此处为临时定义，待扩展
    """

    START = "start"
    END = "end"
    NORMAL = "normal"
    CHOICE = "choice"


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
