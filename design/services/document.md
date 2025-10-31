# Document 文档管理模块

## 1. 模块概述

Document 模块负责处理文档上传、存储、检索和删除等核心功能。该模块分为两层：

- **Router 层** (`apps/routers/document.py`): 提供 RESTful API 接口
- **Service 层** (`apps/services/document.py`): 提供文档管理的核心业务逻辑

### 1.1 核心功能

1. 文档上传到指定对话
2. 查询对话的文档列表（已使用/未使用）
3. 删除单个文档
4. 文档状态管理（unused -> used）
5. 与 RAG 系统集成

### 1.2 技术架构

- **存储**: MinIO (对象存储) + PostgreSQL (元数据)
- **文件类型检测**: python-magic
- **异步处理**: asyncio + asyncer
- **API 框架**: FastAPI

## 2. 数据模型

### 2.1 Document (文档实体)

```python
{
    "id": "uuid",
    "userId": "string",          # 用户标识
    "name": "string",             # 文件名
    "extension": "string",        # MIME 类型
    "size": "float",              # 文件大小 (KB)
    "conversationId": "uuid",     # 所属对话ID
    "createdAt": "datetime"       # 创建时间
}
```

### 2.2 ConversationDocument (对话-文档关联)

```python
{
    "id": "uuid",
    "conversationId": "uuid",     # 对话ID
    "documentId": "uuid",         # 文档ID
    "recordId": "uuid",           # 关联的记录ID
    "isUnused": "boolean",        # 是否未使用
    "associated": "enum"          # 关联类型: QUESTION/ANSWER
}
```

## 3. API 接口文档

### 3.1 上传文档

**接口**: `POST /api/document/{conversation_id}`

**功能**: 上传一个或多个文档到指定对话

**请求参数**:

- Path: `conversation_id` (UUID) - 对话ID
- Body: `multipart/form-data`
  - `documents`: 文件列表

**请求示例**:

```http
POST /api/document/550e8400-e29b-41d4-a716-446655440000
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="documents"; filename="example.pdf"
Content-Type: application/pdf

[binary data]
--boundary--
```

**响应示例** (成功):

```json
{
    "code": 200,
    "message": "上传成功",
    "result": {
        "documents": [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "example.pdf",
                "type": "application/pdf",
                "size": 2048.5
            }
        ]
    }
}
```

**响应 Schema**:

```python
UploadDocumentRsp:
  - code: int
  - message: str
  - result: UploadDocumentMsg
    - documents: list[BaseDocumentItem]
      - id: UUID
      - name: str
      - type: str
      - size: float
```

### 3.2 获取文档列表

**接口**: `GET /api/document/{conversation_id}`

**功能**: 获取指定对话的文档列表

**请求参数**:

- Path: `conversation_id` (UUID) - 对话ID
- Query:
  - `used` (boolean, default=False) - 是否包含已使用文档
  - `unused` (boolean, default=True) - 是否包含未使用文档

**请求示例**:

```http
GET /api/document/550e8400-e29b-41d4-a716-446655440000?used=true
```

**响应示例** (成功):

```json
{
    "code": 200,
    "message": "获取成功",
    "result": {
        "documents": [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "example.pdf",
                "type": "application/pdf",
                "size": 2048.5,
                "status": "USED",
                "created_at": "2025-01-15T10:30:00Z"
            }
        ]
    }
}
```

**响应示例** (无权限):

```json
{
    "code": 403,
    "message": "无权限访问",
    "result": {}
}
```

**文档状态说明**:

- `USED`: 已在对话中使用
- `UNUSED`: 已上传但未使用（RAG 处理成功）
- `PROCESSING`: RAG 正在处理中
- `FAILED`: RAG 处理失败

**响应 Schema**:

```python
ConversationDocumentRsp:
  - code: int
  - message: str
  - result: ConversationDocumentMsg
    - documents: list[ConversationDocumentItem]
      - id: UUID
      - name: str
      - type: str
      - size: float
      - status: DocumentStatus
      - created_at: datetime
```

### 3.3 删除文档

**接口**: `DELETE /api/document/{document_id}`

**功能**: 删除单个未使用的文档

**请求参数**:

- Path: `document_id` (string) - 文档ID

**请求示例**:

```http
DELETE /api/document/123e4567-e89b-12d3-a456-426614174000
```

**响应示例** (成功):

```json
{
    "code": 200,
    "message": "删除成功",
    "result": {}
}
```

**响应示例** (Framework侧删除失败):

```json
{
    "code": 500,
    "message": "删除文件失败",
    "result": {}
}
```

**响应示例** (RAG侧删除失败):

```json
{
    "code": 500,
    "message": "RAG端删除文件失败",
    "result": {}
}
```

**注意**: 只能删除 `isUnused=True` 的文档，已使用的文档无法删除。

## 4. DocumentManager 核心方法

### 4.1 storage_docs

**功能**: 存储多个文档到 MinIO 和数据库

**输入参数**:

- 用户标识符
- 对话ID
- 待上传文件列表

**返回值**: 成功上传的文档信息列表

**处理流程**:

1. 遍历每个上传文件
2. 使用 python-magic 检测文件 MIME 类型
3. 上传到 MinIO 对象存储（bucket名称为"document"）
4. 保存文档元数据到 PostgreSQL 数据库
5. 返回成功上传的文档列表

**MinIO 存储配置**:

- 存储桶名称: document
- 对象名称: 文档的UUID
- 分块大小: 10MB
- 元数据: 使用Base64编码存储文件名

### 4.2 get_unused_docs

**功能**: 获取对话中未使用的文档

**输入参数**: 对话ID

**返回值**: 未使用的文档列表

**查询逻辑**:

从 ConversationDocument 表中查询标记为"未使用"的记录，
然后根据文档ID从 Document 表获取完整的文档信息。

### 4.3 get_used_docs

**功能**: 获取对话中最近 N 次问答使用的文档

**输入参数**:

- 对话ID
- 记录数量（可选，默认10条）
- 文档类型（可选，可筛选"问题"或"答案"关联的文档）

**返回值**: 已使用的文档列表

**查询逻辑**:

1. 查询该对话最近 N 条对话记录
2. 查询这些记录关联的所有文档ID
3. 从 Document 表获取文档详情并去重返回

### 4.4 delete_document

**功能**: 删除未使用的文档

**输入参数**:

- 用户标识符
- 待删除文档ID列表

**返回值**: 无

**删除步骤**:

1. 验证文档所有权（检查文档是否属于当前用户）
2. 验证文档未使用状态（只能删除未使用的文档）
3. 从 PostgreSQL 数据库删除文档记录
4. 从 MinIO 对象存储删除文件数据

**安全机制**:

- 权限控制: 只能删除自己上传的文档
- 状态保护: 只能删除未使用的文档，已使用的文档不可删除

### 4.5 change_doc_status

**功能**: 将文档状态从"未使用"改为"已使用"

**输入参数**:

- 用户标识符
- 对话ID

**返回值**: 无

**使用场景**:

当用户在对话中发送消息并引用已上传的文档时，
系统调用此方法将对话中的所有未使用文档标记为已使用状态。

**处理逻辑**:

查询该对话下所有标记为"未使用"的文档，
将它们的状态批量更新为"已使用"。

### 4.6 save_answer_doc

**功能**: 保存与答案关联的文档

**输入参数**:

- 用户标识符
- 对话记录ID
- 文档关联信息列表

**返回值**: 无

**处理逻辑**:

1. 验证对话记录存在且属于当前用户
2. 更新文档关联表（ConversationDocument），设置：
   - 文档状态为"已使用"
   - 关联类型为"答案"
   - 关联的记录ID

**使用场景**:

当AI生成答案时，如果答案中引用或生成了文档，
系统调用此方法将这些文档与答案记录关联起来。

## 5. 流程图

### 5.1 文档上传流程

```mermaid
flowchart TD
    Start([用户上传文档]) --> A[POST /api/document/:conversation_id]
    A --> B{验证 Session & Token}
    B -->|失败| Err1[返回 401/403]
    B -->|成功| C[DocumentManager.storage_docs]

    C --> D[遍历上传文件]
    D --> E{文件名/大小合法?}
    E -->|否| D
    E -->|是| F[生成 UUID]

    F --> G[检测 MIME 类型]
    G --> H[上传到 MinIO]
    H --> I{上传成功?}
    I -->|否| D
    I -->|是| J[保存元数据到 PostgreSQL]

    J --> K{还有文件?}
    K -->|是| D
    K -->|否| L[发送文件到 RAG 系统]

    L --> M[KnowledgeBaseService.send_file_to_rag]
    M --> N[返回文档列表]
    N --> End([返回 200 OK])

    Err1 --> End
```

### 5.2 文档列表查询流程

```mermaid
flowchart TD
    Start([用户请求文档列表]) --> A[GET /api/document/:conversation_id]
    A --> B{验证权限}
    B -->|无权限| Err1[返回 403]
    B -->|有权限| C{used=true?}

    C -->|是| D[DocumentManager.get_used_docs]
    D --> E[查询最近10条 Record]
    E --> F[查询关联文档]
    F --> G[标记状态为 USED]

    C -->|否| H{unused=true?}
    G --> H

    H -->|是| I[DocumentManager.get_unused_docs]
    I --> J[查询 isUnused=true 的文档]
    J --> K[KnowledgeBaseService.get_doc_status_from_rag]

    K --> L{RAG 状态}
    L -->|success| M[标记为 UNUSED]
    L -->|failed| N[标记为 FAILED]
    L -->|processing| O[标记为 PROCESSING]

    M --> P[合并结果]
    N --> P
    O --> P
    G --> P
    H -->|否| P

    P --> Q[返回文档列表]
    Q --> End([返回 200 OK])

    Err1 --> End
```

### 5.3 文档删除流程

```mermaid
flowchart TD
    Start([用户删除文档]) --> A[DELETE /api/document/:document_id]
    A --> B[DocumentManager.delete_document]

    B --> C{验证文档存在?}
    C -->|否| Err1[返回 500: 删除文件失败]
    C -->|是| D{验证所有权?}
    D -->|否| Err1
    D -->|是| E{验证 isUnused=true?}
    E -->|否| Err1

    E -->|是| F[从 PostgreSQL 删除]
    F --> G[从 MinIO 删除]
    G --> H[KnowledgeBaseService.delete_doc_from_rag]

    H --> I{RAG 删除成功?}
    I -->|否| Err2[返回 500: RAG端删除失败]
    I -->|是| J[返回 200 OK]

    Err1 --> End([结束])
    Err2 --> End
    J --> End
```

### 5.4 文档状态转换流程

```mermaid
stateDiagram-v2
    [*] --> Uploading: 用户上传文档
    Uploading --> Processing: 发送到 RAG

    Processing --> UNUSED: RAG 处理成功
    Processing --> FAILED: RAG 处理失败

    UNUSED --> USED: 用户在对话中引用
    UNUSED --> [*]: 用户删除文档

    USED --> [*]: 删除对话时级联删除
    FAILED --> [*]: 用户删除文档

    note right of Processing
        RAG 系统处理中
        状态: PROCESSING
    end note

    note right of UNUSED
        已上传但未使用
        可被删除
    end note

    note right of USED
        已在对话中使用
        不可单独删除
    end note
```

## 6. 时序图

### 6.1 文档上传完整时序

```mermaid
sequenceDiagram
    actor User as 用户
    participant API as FastAPI Router
    participant Auth as 认证中间件
    participant DM as DocumentManager
    participant MinIO as MinIO 存储
    participant DB as PostgreSQL
    participant RAG as RAG 系统

    User->>API: POST /api/document/:conv_id
    API->>Auth: verify_session()
    Auth-->>API: ✓ user_id
    API->>Auth: verify_personal_token()
    Auth-->>API: ✓ personal_token

    API->>DM: storage_docs(user_id, conv_id, files)

    loop 每个文件
        DM->>DM: 检测 MIME 类型
        DM->>MinIO: upload_file(doc_id, data)
        MinIO-->>DM: ✓ 存储成功
        DM->>DB: INSERT Document
        DB-->>DM: ✓ 保存成功
    end

    DM-->>API: 返回文档列表

    API->>API: auth_header = request.session.session_id || request.state.personal_token
    API->>RAG: send_file_to_rag(auth_header, docs)
    RAG-->>API: ✓ 接收成功

    API->>User: 200 OK + 文档列表

    Note over RAG: 异步处理文档<br/>解析、向量化、索引
```

### 6.2 文档列表查询时序

```mermaid
sequenceDiagram
    actor User as 用户
    participant API as FastAPI Router
    participant CM as ConversationManager
    participant DM as DocumentManager
    participant DB as PostgreSQL
    participant RAG as RAG 系统

    User->>API: GET /api/document/:conv_id?used=true&unused=true

    API->>CM: verify_conversation_access(user_id, conv_id)
    CM->>DB: SELECT Conversation
    DB-->>CM: Conversation 数据
    CM-->>API: ✓ 有权限

    alt used=true
        API->>DM: get_used_docs(conv_id)
        DM->>DB: SELECT Record (最近10条)
        DB-->>DM: Record 列表
        DM->>DB: SELECT ConversationDocument
        DB-->>DM: 关联的文档ID
        DM->>DB: SELECT Document
        DB-->>DM: 文档详情
        DM-->>API: 已使用文档列表 (状态=USED)
    end

    alt unused=true
        API->>DM: get_unused_docs(conv_id)
        DM->>DB: SELECT ConversationDocument (isUnused=true)
        DB-->>DM: 未使用文档ID
        DM->>DB: SELECT Document
        DB-->>DM: 文档详情
        DM-->>API: 未使用文档列表

        API->>API: auth_header = request.session.session_id || request.state.personal_token
        API->>RAG: get_doc_status_from_rag(auth_header, doc_ids)
        RAG-->>API: 文档处理状态列表

        loop 每个未使用文档
            alt RAG状态=success
                API->>API: 标记为 UNUSED
            else RAG状态=failed
                API->>API: 标记为 FAILED
            else RAG状态=processing
                API->>API: 标记为 PROCESSING
            end
        end
    end

    API->>API: 合并所有文档
    API->>User: 200 OK + 完整文档列表
```

### 6.3 文档删除时序

```mermaid
sequenceDiagram
    actor User as 用户
    participant API as FastAPI Router
    participant DM as DocumentManager
    participant DB as PostgreSQL
    participant MinIO as MinIO 存储
    participant RAG as RAG 系统

    User->>API: DELETE /api/document/:doc_id

    API->>DM: delete_document(user_id, [doc_id])

    DM->>DB: SELECT Document (验证所有权)
    DB-->>DM: Document 数据

    DM->>DB: SELECT ConversationDocument (验证未使用)
    DB-->>DM: ConversationDocument 数据

    alt 验证失败
        DM-->>API: 返回 None
        API->>User: 500 删除文件失败
    else 验证成功
        DM->>DB: DELETE ConversationDocument
        DB-->>DM: ✓
        DM->>DB: DELETE Document
        DB-->>DM: ✓
        DM->>MinIO: delete_file("document", doc_id)
        MinIO-->>DM: ✓
        DM-->>API: 删除成功

        API->>API: auth_header = request.session.session_id || request.state.personal_token
        API->>RAG: delete_doc_from_rag(auth_header, [doc_id])
        RAG-->>API: 删除结果

        alt RAG删除失败
            API->>User: 500 RAG端删除失败
        else RAG删除成功
            API->>User: 200 OK 删除成功
        end
    end
```

### 6.4 文档状态变更时序

```mermaid
sequenceDiagram
    actor User as 用户
    participant Chat as 对话服务
    participant DM as DocumentManager
    participant DB as PostgreSQL

    User->>Chat: 发送消息引用文档

    Chat->>DM: change_doc_status(user_id, conv_id)

    DM->>DB: SELECT Conversation (验证权限)
    DB-->>DM: Conversation 数据

    DM->>DB: SELECT ConversationDocument (isUnused=true)
    DB-->>DM: 未使用文档列表

    loop 每个未使用文档
        DM->>DB: UPDATE isUnused = false
        DB-->>DM: ✓
    end

    DM-->>Chat: 状态更新完成

    Note over Chat: 继续处理对话<br/>生成回答

    Chat->>DM: save_answer_doc(user_id, record_id, doc_infos)

    DM->>DB: SELECT Record (验证)
    DB-->>DM: Record 数据

    loop 每个答案关联文档
        DM->>DB: UPDATE ConversationDocument
        DB-->>DM: ✓
    end

    DM-->>Chat: 保存完成
    Chat->>User: 返回答案
```

## 7. 架构图

### 7.1 整体架构

```mermaid
graph TB
    subgraph "客户端"
        UI[前端界面]
    end

    subgraph "API 层"
        Router[document.py Router]
        Auth[认证中间件]
    end

    subgraph "Service 层"
        DM[DocumentManager]
        CM[ConversationManager]
        KB[KnowledgeBaseService]
    end

    subgraph "存储层"
        MinIO[(MinIO<br/>对象存储)]
        PG[(PostgreSQL<br/>关系数据库)]
    end

    subgraph "外部服务"
        RAG[RAG 系统]
    end

    UI -->|HTTP/HTTPS| Router
    Router --> Auth
    Auth --> DM
    Router --> CM
    Router --> KB

    DM --> MinIO
    DM --> PG
    CM --> PG
    KB --> RAG

    style Router fill:#e1f5ff
    style DM fill:#fff3e0
    style MinIO fill:#f3e5f5
    style PG fill:#f3e5f5
    style RAG fill:#e8f5e9
```

### 7.2 数据库关系图

```mermaid
erDiagram
    Document ||--o{ ConversationDocument : "1:N"
    Conversation ||--o{ ConversationDocument : "1:N"
    Record ||--o{ ConversationDocument : "1:N"

    Document {
        uuid id PK
        string userId
        string name
        string extension
        float size
        uuid conversationId FK
        datetime createdAt
    }

    ConversationDocument {
        uuid id PK
        uuid conversationId FK
        uuid documentId FK
        uuid recordId FK
        boolean isUnused
        enum associated
    }

    Conversation {
        uuid id PK
        string userId
        string title
        datetime createdAt
    }

    Record {
        uuid id PK
        uuid conversationId FK
        string userId
        string content
        datetime createdAt
    }
```

## 8. 错误处理

### 8.1 常见错误码

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| 400 | 请求参数错误 | 检查请求格式和参数 |
| 401 | 未认证 | 检查 Session Token |
| 403 | 无权限访问 | 验证对话所有权 |
| 404 | 资源不存在 | 确认文档/对话ID正确 |
| 500 | 服务器内部错误 | 查看日志，联系管理员 |

### 8.2 异常处理机制

**文档上传异常处理**:

在上传多个文档时，如果某个文档上传失败，系统会跳过该文档继续处理其他文档，
并记录详细错误日志。最终只返回成功上传的文档列表。

**特点**:

- 部分失败不影响整体流程
- 只返回成功上传的文档
- 详细错误日志便于排查

## 9. 集成说明

### 9.1 与 RAG 系统集成

**认证方式**:

所有 RAG 系统调用使用 `auth_header` 参数进行认证。
`auth_header` 的值优先使用 `request.session.session_id`，若不存在则使用 `request.state.personal_token`。

**文档上传后发送到 RAG**:

调用 `KnowledgeBaseService.send_file_to_rag(auth_header, docs)` 方法，
将文档发送到 RAG 系统进行异步处理（解析、向量化、索引）。

**查询文档处理状态**:

调用 `KnowledgeBaseService.get_doc_status_from_rag(auth_header, doc_ids)` 方法，
获取文档在 RAG 系统中的处理状态。

**从 RAG 删除文档**:

调用 `KnowledgeBaseService.delete_doc_from_rag(auth_header, doc_ids)` 方法，
从 RAG 系统中删除文档的索引数据。

### 9.2 RAG 状态映射

| RAG 状态 | Framework 状态 | 说明 |
|----------|----------------|------|
| success | UNUSED | 文档已解析，可供检索 |
| failed | FAILED | 文档解析失败 |
| processing | PROCESSING | 文档处理中 |
| - | USED | 已在对话中引用 |

## 10. 配置参数

### 10.1 MinIO 配置

- **BUCKET_NAME**: "document"
- **PART_SIZE**: 10MB (10 \* 1024 \* 1024 字节)

### 10.2 查询配置

- **DEFAULT_RECORD_NUM**: 10 (获取最近10条记录的文档)

### 10.3 文件名编码

使用 Base64 编码存储文件名，避免特殊字符导致的问题。
