# Tag模块设计文档

## 概述

Tag 模块是 openEuler Intelligence 框架中的用户标签管理系统，用于管理用户分类标签的定义、更新和删除操作，并提供用户标签关联功能。当前公开的管理 API 仅支持查询/修改/删除已有标签，新增标签需通过后端内部调用 `TagManager.add_tag` 完成。

## 核心功能

- **标签管理**: 查询、更新、删除标签（新增操作需后端内部调用）
- **用户标签关联**: 管理用户与标签的关联关系
- **标签统计**: 统计标签使用频次
- **权限控制**: 仅管理员可进行标签管理操作

## 数据模型

```mermaid
erDiagram
    framework_user ||--o{ framework_user_tag : "用户拥有标签"
    framework_tag ||--o{ framework_user_tag : "标签被用户使用"
    
    framework_user {
        BigInteger id PK "主键"
        string userId UK "用户标识"
        datetime lastLogin "最后登录时间"
        boolean isActive "是否活跃"
        boolean isWhitelisted "是否白名单"
        integer credit "风控分"
        string personalToken "个人令牌"
        string functionLLM "函数模型ID"
        string embeddingLLM "向量模型ID"
        boolean autoExecute "自动执行"
    }
    
    framework_tag {
        BigInteger id PK "主键"
        string name UK "标签名称(唯一索引)"
        string definition "标签定义"
        datetime updatedAt "更新时间(时区感知)"
    }
    
    framework_user_tag {
        BigInteger id PK "主键"
        string userId FK "用户标识(外键)"
        BigInteger tag FK "标签ID(外键)"
        integer count "标签使用频次(默认0)"
    }
```

### 数据表说明

- **framework_tag**: 标签基础信息表，存储标签的定义和元数据
- **framework_user_tag**: 用户标签关联表，记录用户与标签的多对多关系及使用频次
- **framework_user**: 用户基础信息表，通过userId字段与标签系统关联

## API接口

### 管理接口 (需要管理员权限)

#### GET /api/tag

- **功能**: 获取所有标签列表
- **权限**: 管理员
- **返回**: 标签信息列表

#### POST /api/tag

- **功能**: 更新已有标签定义
- **权限**: 管理员
- **请求体**: `PostTagData`
  - `tag`: 标签名称
  - `description`: 标签描述
- **逻辑**: 标签存在时更新 `definition` 和 `updatedAt`；标签不存在时抛出 `ValueError`（接口返回 500）。

#### DELETE /api/tag

- **功能**: 删除标签
- **权限**: 管理员
- **请求体**: `PostTagData`
- **逻辑**: 根据标签名称删除对应标签

## 服务层

### TagManager类

#### 静态方法

- `get_all_tag()`: 获取所有标签
- `get_tag_by_name(name)`: 根据名称获取标签
- `get_tag_by_user_id(user_id)`: 获取用户的所有标签
- `add_tag(data)`: 添加新标签（当前路由未调用）
- `update_tag_by_name(data)`: 更新标签定义，标签不存在时抛出 `ValueError`
- `delete_tag(data)`: 删除标签

## 时序图

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Router as 路由层
    participant Service as TagManager
    participant DB as 数据库

    Note over Client, DB: 标签查询流程
    Client->>Router: GET /api/tag
    Router->>Service: get_all_tag()
    Service->>DB: SELECT * FROM framework_tag
    DB-->>Service: 返回标签列表
    Service-->>Router: 返回标签数据
    Router-->>Client: 返回JSON响应

    Note over Client, DB: 标签更新流程
    Client->>Router: POST /api/tag
    Router->>Service: update_tag_by_name(data)
    Service->>DB: SELECT * FROM framework_tag WHERE name=?
    DB-->>Service: 返回查询结果
    alt 标签不存在
        Service-->>Router: 抛出异常
        Router-->>Client: 返回500错误
    else 标签存在
        Service->>DB: UPDATE framework_tag SET definition=?, updatedAt=?
        DB-->>Service: 操作完成
        Service-->>Router: 返回操作结果
        Router-->>Client: 返回成功响应
    end

    Note over Client, DB: 标签删除流程
    Client->>Router: DELETE /api/tag
    Router->>Service: delete_tag(data)
    Service->>DB: SELECT * FROM framework_tag WHERE name=?
    DB-->>Service: 返回查询结果
    alt 标签存在
        Service->>DB: DELETE FROM framework_tag WHERE id=?
        DB-->>Service: 删除完成
        Service-->>Router: 删除成功
    else 标签不存在
        Service-->>Router: 抛出异常
    end
    Router-->>Client: 返回响应结果

    Note over Client, DB: 用户标签查询流程
    Client->>Router: GET /api/user/tag
    Router->>Service: get_tag_by_user_id(user_id)
    Service->>DB: SELECT * FROM framework_user_tag WHERE userId=?
    DB-->>Service: 返回用户标签关联
    loop 遍历用户标签
        Service->>DB: SELECT * FROM framework_tag WHERE id=?
        DB-->>Service: 返回标签详情
    end
    Service-->>Router: 返回用户标签列表
    Router-->>Client: 返回JSON响应
```

## 流程图

```mermaid
flowchart TD
    A[客户端请求] --> B{权限验证}
    B -->|验证失败| C[返回403错误]
    B -->|验证成功| D{请求类型}
    
    D -->|GET| E[获取标签列表]
    D -->|POST| F[更新标签]
    D -->|DELETE| G[删除标签]
    
    E --> H[TagManager.get_all_tag]
    H --> I[查询framework_tag表]
    I --> J[返回所有标签]
    J --> K[返回JSON响应]
    
    F --> L[TagManager.update_tag_by_name]
    L --> M{标签是否存在}
    M -->|不存在| N[返回500错误]
    M -->|存在| O[更新标签定义]
    O --> Q[UPDATE操作]
    N --> R[返回错误响应]
    Q --> R[返回成功响应]
    
    G --> S[TagManager.delete_tag]
    S --> T{标签是否存在}
    T -->|不存在| U[抛出异常]
    T -->|存在| V[DELETE操作]
    U --> W[返回错误响应]
    V --> X[返回成功响应]
    
    style A fill:#e1f5fe
    style K fill:#c8e6c9
    style R fill:#c8e6c9
    style X fill:#c8e6c9
    style C fill:#ffcdd2
    style U fill:#ffcdd2
    style W fill:#ffcdd2
```

## 数据流转图

```mermaid
flowchart LR
    subgraph "前端层"
        A[管理界面]
        B[API调用]
    end
    
    subgraph "API层"
        C[FastAPI Router]
        D[权限验证]
        E[请求验证]
    end
    
    subgraph "服务层"
        F[TagManager]
        G[业务逻辑]
        H[数据验证]
    end
    
    subgraph "数据层"
        I[PostgreSQL]
        J[Tag表]
        K[UserTag表]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    I --> K
    
    J -.->|标签信息| K
    K -.->|关联数据| F
    F -.->|处理结果| C
    C -.->|响应数据| A
    
    style A fill:#e3f2fd
    style F fill:#f3e5f5
    style I fill:#e8f5e8
```

## 安全考虑

1. **权限控制**: 所有标签管理操作需要管理员权限
2. **数据验证**: 输入数据长度和格式验证
