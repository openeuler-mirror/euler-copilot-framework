# FlowManager 模块设计文档

## 1. 概述

FlowManager 模块是 openEuler Intelligence 框架中负责工作流（Flow）管理的核心模块。当前实现重点覆盖已有 Flow 的读取、更新、删除，以及节点元数据管理、服务管理等功能（独立的“新建 Flow”流程尚未单独提供专用接口）。

### 1.1 核心组件

- **FlowManager**: 工作流管理的主要服务类，提供工作流和节点的 CRUD 操作
- **FlowServiceManager**: 工作流拓扑验证和处理服务
- **FlowLoader**: 工作流配置文件的加载和保存
- **Flow API Router**: FastAPI 路由层，提供 RESTful API 接口

## 2. 数据模型

### 2.1 核心数据结构

```mermaid
classDiagram
    class Flow {
        +str name
        +str description
        +FlowCheckStatus checkStatus
        +FlowBasicConfig basicConfig
        +FlowError onError
        +dict~UUID,Step~ steps
        +list~Edge~ edges
    }

    class Step {
        +str node
        +str type
        +str name
        +str description
        +PositionItem pos
        +dict params
    }

    class Edge {
        +UUID id
        +str edge_from
        +str edge_to
        +EdgeType edge_type
    }

    class FlowBasicConfig {
        +UUID startStep
        +UUID endStep
        +PositionItem focusPoint
    }

    class FlowCheckStatus {
        +bool debug
        +bool connectivity
    }

    class FlowItem {
        +str flow_id
        +str name
        +str description
        +bool enable
        +list~NodeItem~ nodes
        +list~EdgeItem~ edges
        +FlowBasicConfig basic_config
        +FlowCheckStatus check_status
    }

    Flow --> Step
    Flow --> Edge
    Flow --> FlowBasicConfig
    Flow --> FlowCheckStatus
    FlowItem --> NodeItem
    FlowItem --> EdgeItem
```

### 2.2 数据库模型

```mermaid
erDiagram
    App ||--o{ Flow : contains
    Flow {
        string id PK
        uuid appId FK
        string name
        text description
        string path
        bool debug
        bool enabled
        datetime updatedAt
    }

    App {
        uuid id PK
        string name
        string author
    }

    NodeInfo {
        string id PK
        uuid serviceId FK
        string callId
        string name
        text description
        datetime updatedAt
    }

    Service {
        uuid id PK
        string name
        string author
        datetime updatedAt
    }

    UserFavorite {
        string userId
        uuid itemId
        string favouriteType
    }

    AppHashes {
        uuid appId FK
        string filePath
        string hash
    }

    Service ||--o{ NodeInfo : contains
    App ||--o{ AppHashes : tracks
```

## 3. 核心功能

### 3.1 工作流管理流程

```mermaid
sequenceDiagram
    participant Client
    participant API as Flow Router
    participant FM as FlowManager
    participant FSM as FlowServiceManager
    participant FL as FlowLoader
    participant DB as PostgreSQL
    participant FS as FileSystem

    Note over Client,FS: 获取工作流
    Client->>API: GET /api/flow?appId=xxx&flowId=xxx
    API->>FM: get_flow_by_app_and_flow_id()
    FM->>DB: 查询 Flow 记录
    FM->>FL: load(app_id, flow_id)
    FL->>FS: 读取 YAML 文件
    FL->>FL: 验证基本字段
    FL->>FL: 处理边(edges)
    FL->>FL: 处理步骤(steps)
    FL->>DB: 更新数据库记录
    FL-->>FM: 返回 Flow 配置
    FM->>FM: 转换为 FlowItem
    FM-->>API: 返回 FlowItem
    API-->>Client: 返回响应

    Note over Client,FS: 更新工作流
    Client->>API: PUT /api/flow?appId=xxx&flowId=xxx
    API->>FSM: remove_excess_structure_from_flow()
    FSM-->>API: 清理后的 FlowItem
    API->>FSM: validate_flow_illegal()
    FSM->>FSM: 验证节点ID唯一性
    FSM->>FSM: 验证边的合法性
    FSM-->>API: 验证通过
    API->>FSM: validate_flow_connectivity()
    FSM->>FSM: BFS 检查连通性
    FSM-->>API: 返回连通性状态
    API->>FM: put_flow_by_app_and_flow_id()
    FM->>FM: 转换 FlowItem 为 Flow
    FM->>FL: 检查旧配置
    FM->>FM: is_flow_config_equal()
    FM->>FL: save(app_id, flow_id, flow)
    FL->>FS: 写入 YAML 文件
    FL->>DB: 以 appId 为范围删除旧 Flow 记录并写入最新元数据
    FL->>DB: 更新 AppHashes
    FL-->>FM: 保存成功
    FM-->>API: 更新完成
    API-->>Client: 返回更新结果
```

Note: 上述流程不会自动触发向量索引同步，如需同步需在业务层额外调用 `_update_vector` 或传入 embedding 模型。

### 3.2 节点和服务管理流程

```mermaid
sequenceDiagram
    participant Client
    participant API as Flow Router
    participant FM as FlowManager
    participant DB as PostgreSQL
    participant NM as NodeManager

    Note over Client,NM: 获取用户服务列表
    Client->>API: GET /api/flow/service
    API->>FM: get_service_by_user_id(user_id)
    FM->>DB: 查询用户收藏的服务
    FM->>DB: 查询用户上传的服务
    FM->>DB: 去重并查询服务详情
    loop 每个服务
        FM->>FM: get_node_id_by_service_id()
        FM->>DB: 查询服务下的节点
        FM->>FM: 格式化节点元数据
    end
    FM-->>API: 返回服务及节点列表
    API-->>Client: 返回响应

    Note over Client,NM: 获取节点详细信息
    Client->>FM: get_node_by_node_id(node_id)
    FM->>DB: 查询节点记录
    FM->>NM: get_node_params(node_id)
    NM-->>FM: 返回参数 schema
    FM->>FM: 创建空槽位(empty slot)
    FM->>FM: 提取类型描述
    FM-->>Client: 返回节点元数据
```

### 3.3 工作流验证流程

```mermaid
flowchart TD
    Start([开始验证]) --> ValidateNodes[验证节点ID唯一性]
    ValidateNodes --> CheckStart{检查起始节点}
    CheckStart -->|存在| CheckEnd{检查终止节点}
    CheckStart -->|不存在| Error1[抛出异常: 起始节点不存在]
    CheckEnd -->|存在| ValidateEdges[验证边的合法性]
    CheckEnd -->|不存在| Error2[抛出异常: 终止节点不存在]

    ValidateEdges --> CheckEdgeId{边ID唯一?}
    CheckEdgeId -->|否| Error3[抛出异常: 边ID重复]
    CheckEdgeId -->|是| CheckSelfLoop{自环?}
    CheckSelfLoop -->|是| Error4[抛出异常: 起止节点相同]
    CheckSelfLoop -->|否| CheckBranch{分支合法?}
    CheckBranch -->|否| Error5[抛出异常: 分支非法]
    CheckBranch -->|是| ValidateConn[验证连通性]

    ValidateConn --> BFS[BFS遍历图]
    BFS --> CheckReachable{所有节点可达?}
    CheckReachable -->|否| ConnFalse[连通性=False]
    CheckReachable -->|是| CheckEndReachable{终止节点可达?}
    CheckEndReachable -->|否| ConnFalse
    CheckEndReachable -->|是| CheckOutEdge{非终止节点都有出边?}
    CheckOutEdge -->|否| ConnFalse
    CheckOutEdge -->|是| ConnTrue[连通性=True]

    ConnTrue --> Success([验证成功])
    ConnFalse --> Success

    Error1 --> End([结束])
    Error2 --> End
    Error3 --> End
    Error4 --> End
    Error5 --> End
    Success --> End
```

### 3.4 工作流删除流程

```mermaid
sequenceDiagram
    participant Client
    participant API as Flow Router
    participant FM as FlowManager
    participant FL as FlowLoader
    participant DB as PostgreSQL
    participant FS as FileSystem
    participant AL as AppLoader

    Client->>API: DELETE /api/flow?appId=xxx&flowId=xxx
    API->>API: 验证用户权限
    API->>FM: delete_flow_by_app_and_flow_id()

    FM->>FL: delete(app_id, flow_id)
    FL->>FS: 检查文件是否存在
    FL->>FS: 删除 YAML 文件
    FL->>DB: 删除 Flow 记录
    FL->>DB: 删除向量数据(仅当调用方向 FlowLoader.delete 传入 embedding_model 时)
    FL->>DB: commit
    FL-->>FM: 删除成功

    FM->>DB: 删除 AppHashes 记录
    FM->>AL: read_metadata(app_id)
    AL-->>FM: 返回 AppMetadata
    FM->>FM: 从 hashes 中移除 flow
    FM->>FM: 从 flows 列表中移除
    FM->>AL: save(metadata, app_id)
    AL->>FS: 更新 metadata.yaml
    AL->>DB: 更新数据库
    AL-->>FM: 保存成功

    FM-->>API: 删除完成
    API-->>Client: 返回删除结果
```

## 4. API 接口

### 4.1 接口列表

| 方法 | 路径 | 功能 | 认证 |
|------|------|------|------|
| GET | `/api/flow/service` | 获取用户可访问的服务及节点列表 | 需要 |
| GET | `/api/flow` | 获取指定工作流的拓扑结构 | 需要 |
| PUT | `/api/flow` | 更新工作流拓扑结构 | 需要 |
| DELETE | `/api/flow` | 删除工作流 | 需要 |

### 4.2 接口详情

#### 4.2.1 获取服务列表

**HTTP 请求：**

```http
GET /api/flow/service
Authorization: Bearer <token>
```

**返回示例：**

```json
{
  "code": 200,
  "message": "Node所在Service获取成功",
  "result": {
    "services": [
      {
        "serviceId": "00000000-0000-0000-0000-000000000000",
        "name": "系统",
        "data": [
          {
            "nodeId": "start",
            "callId": "Start",
            "name": "开始",
            "updatedAt": 1234567890.123
          }
        ],
        "createdAt": null
      }
    ]
  }
}
```

#### 4.2.2 获取工作流

**HTTP 请求：**

```http
GET /api/flow?appId={uuid}&flowId={string}
Authorization: Bearer <token>
```

**返回示例：**

```json
{
  "code": 200,
  "message": "应用的Workflow获取成功",
  "result": {
    "flow": {
      "flowId": "main",
      "name": "主工作流",
      "description": "这是一个示例工作流",
      "enable": true,
      "nodes": [...],
      "edges": [...],
      "basicConfig": {
        "startStep": "uuid",
        "endStep": "uuid",
        "focusPoint": {"x": 0, "y": 0}
      },
      "checkStatus": {
        "debug": false,
        "connectivity": true
      }
    }
  }
}
```

#### 4.2.3 更新工作流

**HTTP 请求：**

```http
PUT /api/flow?appId={uuid}&flowId={string}
Authorization: Bearer <token>
Content-Type: application/json

{
  "flow": {
    "flowId": "main",
    "name": "主工作流",
    "nodes": [...],
    "edges": [...],
    "basicConfig": {...}
  }
}
```

**返回示例：**

```json
{
  "code": 200,
  "message": "应用下流更新成功",
  "result": {
    "flow": {...}
  }
}
```

#### 4.2.4 删除工作流

**HTTP 请求：**

```http
DELETE /api/flow?appId={uuid}&flowId={string}
Authorization: Bearer <token>
```

**返回示例：**

```json
{
  "code": 200,
  "message": "应用下流程删除成功",
  "result": {
    "flowId": "main"
  }
}
```

## 5. 核心类详解

### 5.1 FlowManager

位置：`apps/services/flow.py`

**主要方法：**

| 方法 | 功能 | 参数 | 返回值 |
|------|------|------|--------|
| `get_flows_by_app_id` | 获取应用的所有工作流 | `app_id: UUID` | `list[FlowInfo]` |
| `get_node_id_by_service_id` | 获取服务下的节点列表 | `service_id: UUID` | `list[NodeMetaDataBase]` |
| `get_service_by_user_id` | 获取用户的服务列表 | `user_id: str` | `list[NodeServiceItem]` |
| `get_node_by_node_id` | 获取节点详细信息 | `node_id: str` | `NodeMetaDataItem` |
| `get_flow_by_app_and_flow_id` | 获取工作流详情 | `app_id: UUID, flow_id: str` | `FlowItem` |
| `put_flow_by_app_and_flow_id` | 保存/更新工作流 | `app_id: UUID, flow_id: str, flow_item: FlowItem` | `None` |
| `delete_flow_by_app_and_flow_id` | 删除工作流 | `app_id: UUID, flow_id: str` | `None` |
| `update_flow_debug_by_app_and_flow_id` | 更新调试状态 | `app_id: UUID, flow_id: str, debug: bool` | `bool` |
| `is_flow_config_equal` | 比较两个工作流配置是否相等 | `flow_config_1: Flow, flow_config_2: Flow` | `bool` |

### 5.2 FlowServiceManager

位置：`apps/services/flow_service.py`

**主要方法：**

| 方法 | 功能 | 异常 |
|------|------|------|
| `remove_excess_structure_from_flow` | 移除工作流中的多余结构（无效边） | `FlowBranchValidationError` |
| `validate_flow_illegal` | 验证工作流是否合法 | `FlowNodeValidationError`, `FlowEdgeValidationError` |
| `validate_flow_connectivity` | 验证工作流连通性（BFS） | - |
| `_validate_node_ids` | 验证节点ID唯一性 | `FlowNodeValidationError` |
| `_validate_edges` | 验证边的合法性 | `FlowEdgeValidationError` |

### 5.3 FlowLoader

位置：`apps/scheduler/pool/loader/flow.py`

**主要方法：**

| 方法 | 功能 | 异常 |
|------|------|------|
| `load` | 从文件系统加载工作流，并刷新数据库中的基本元数据 | `FileNotFoundError`, `RuntimeError` |
| `save` | 保存工作流到文件系统，并在数据库中以“先删后插”方式写入最新元数据 | - |
| `delete` | 删除工作流文件和数据库记录（不传 embedding_model 时不会触发向量清理） | - |
| `_load_yaml_file` | 加载YAML文件 | - |
| `_validate_basic_fields` | 验证基本字段 | - |
| `_process_edges` | 将 YAML 的 `from/to/type` 转换为内部字段，分支通过 `stepId.branchId` 字符串表示 | - |
| `_process_steps` | 处理步骤的类型和文档信息 | `ValueError` |
| `_update_db` | 同步 FlowInfo 和 AppHashes（覆盖同一 appId 的旧记录） | - |
| `_update_vector` | 预留的向量更新方法（当前调用路径未触发） | - |

> **实现提示**
>
> - FlowLoader 的 `save`/`load` 都会调用 `_update_db`，该方法会删除同一 `appId` 下的旧 `FlowInfo` 记录后再写入新记录，调用侧需要在保存多个 Flow 时显式传入完整集合。
> - 向量数据的增量更新需要外部显式调用 `_update_vector` 或在删除时传入 embedding 模型；默认调用路径不会同步向量索引。

## 6. 状态管理

### 6.1 工作流状态

```mermaid
stateDiagram-v2
    [*] --> Created: 创建工作流
    Created --> Editing: 编辑中
    Editing --> Validating: 保存
    Validating --> Invalid: 验证失败
    Validating --> Valid: 验证成功
    Invalid --> Editing: 继续编辑
    Valid --> Testing: 开始调试
    Testing --> Debugged: 调试成功
    Testing --> Valid: 调试失败
    Debugged --> Published: 发布
    Published --> [*]: 删除
    Editing --> [*]: 删除
    Valid --> [*]: 删除

    note right of Valid
        connectivity = true
        debug = false
    end note

    note right of Debugged
        connectivity = true
        debug = true
    end note
```

### 6.2 工作流检查状态

- **debug**：是否经过调试（当工作流内容修改后会重置为 false）
- **connectivity**：图的连通性检查
  - 起始节点到终止节点是否联通
  - 除终止节点外所有节点是否都有出边
  - 所有节点是否都可从起始节点到达

## 7. 数据转换

### 7.1 FlowItem 与 Flow 转换

```mermaid
flowchart LR
    subgraph Frontend
        FlowItem[FlowItem<br/>前端数据结构]
    end

    subgraph Backend
        Flow[Flow<br/>配置数据结构]
    end

    subgraph Storage
        YAML[YAML文件]
        DB[(数据库)]
    end

    FlowItem -->|put_flow| Flow
    Flow -->|get_flow| FlowItem
    Flow -->|save| YAML
    YAML -->|load| Flow
    Flow -->|_update_db| DB
    DB -->|query| Flow
```

**转换关键点：**

1. **NodeItem → Step**
   - `step_id` 作为字典 key
   - `node_id` 映射到 `node`
   - `call_id` 映射到 `type`
   - `parameters["input_parameters"]` 映射到 `params`

2. **EdgeItem → Edge**
   - `source_branch` + `branch_id` 组合成 `edge_from`（用 "." 连接）
   - `target_branch` 映射到 `edge_to`
   - `type` 转换为 `EdgeType` 枚举

3. **边格式处理**
   - 存储：`edge_from = "step_id.branch_id"`（有分支时）
   - 存储：`edge_from = "step_id"`（无分支时）
   - 解析：按 "." 分割，长度为 2 表示有分支

## 8. 异常处理

### 8.1 异常类型

| 异常类 | 触发条件 | 处理方式 |
|--------|----------|----------|
| `FlowNodeValidationError` | 节点ID重复、起始/终止节点不存在 | 返回400错误 |
| `FlowEdgeValidationError` | 边ID重复、自环、分支非法 | 返回400错误 |
| `FlowBranchValidationError` | 分支字段缺失/为空、分支重复、非法字符 | 返回400错误 |
| `ValueError` | 应用不存在、工作流不存在、配置错误 | 返回404/500错误 |
| `FileNotFoundError` | 工作流文件不存在 | 返回404错误 |
| `RuntimeError` | YAML文件格式错误 | 返回500错误 |

### 8.2 错误处理流程

```mermaid
flowchart TD
    Request[API请求] --> Auth{权限验证}
    Auth -->|失败| Return403[返回403 Forbidden]
    Auth -->|成功| Validate{数据验证}
    Validate -->|失败| Return400[返回400 Bad Request]
    Validate -->|成功| Process[处理业务逻辑]
    Process -->|异常| CatchError{捕获异常}
    CatchError -->|FlowValidationError| Return400
    CatchError -->|FileNotFoundError| Return404[返回404 Not Found]
    CatchError -->|ValueError| Return404
    CatchError -->|其他异常| Return500[返回500 Internal Server Error]
    Process -->|成功| Return200[返回200 OK]
```

## 9. 安全性

- 输入参数使用 Pydantic 模型验证
- 分支ID禁止包含"."等非法字符
- 节点/边ID唯一性检查
- YAML文件格式验证

## 10. 配置示例

YAML配置文件示例：

```yaml
name: 示例工作流
description: 这是一个示例工作流配置
checkStatus:
  debug: false
  connectivity: true
basicConfig:
  startStep: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  endStep: f1e2d3c4-b5a6-7890-dcba-fe0987654321
  focusPoint:
    x: 0.0
    y: 0.0
onError:
  use_llm: true
steps:
  a1b2c3d4-e5f6-7890-abcd-ef1234567890:
    type: Start
    node: start
    name: 开始
    description: 工作流起始节点
    pos:
      x: 100.0
      y: 100.0
    params: {}
  b2c3d4e5-f6a7-8901-bcde-f12345678901:
    type: ApiCall
    node: api_node_123
    name: API调用
    description: 调用外部API
    pos:
      x: 300.0
      y: 100.0
    params:
      url: https://api.example.com
      method: GET
  f1e2d3c4-b5a6-7890-dcba-fe0987654321:
    type: End
    node: end
    name: 结束
    description: 工作流结束节点
    pos:
      x: 500.0
      y: 100.0
    params: {}
edges:
  - id: edge001
    edge_from: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    edge_to: b2c3d4e5-f6a7-8901-bcde-f12345678901
    edge_type: NORMAL
  - id: edge002
    edge_from: b2c3d4e5-f6a7-8901-bcde-f12345678901
    edge_to: f1e2d3c4-b5a6-7890-dcba-fe0987654321
    edge_type: NORMAL
```

## 11. 文件存储结构

```text
data_dir/
└── semantics/
    └── app/
        └── {app_id}/
            ├── metadata.yaml         # 应用元数据
            └── flow/
                ├── main.yaml         # 主工作流
                ├── {flow_id}.yaml    # 其他工作流
                └── ...
```
