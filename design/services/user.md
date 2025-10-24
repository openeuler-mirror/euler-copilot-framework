# User模块设计文档

## 概述

User 模块是 openEuler Intelligence 框架中的核心用户管理模块，负责处理用户信息的CRUD操作、用户LLM配置管理、用户标签管理等功能。该模块采用分层架构设计，包含数据模型层、服务层和路由层。

## 架构设计

### 模块结构

```text
apps/
├── models/user.py          # 用户数据模型
├── services/user.py        # 用户服务层
├── routers/user.py         # 用户路由层
├── schemas/
│   ├── user.py            # 用户响应数据结构
│   ├── request_data.py    # 用户请求数据结构
│   └── response_data.py   # 通用响应数据结构
└── services/
    ├── user_tag.py        # 用户标签服务
    ├── llm.py            # LLM管理服务
    └── personal_token.py  # 个人令牌服务
```

### 数据模型关系

```mermaid
erDiagram
    User ||--o{ UserFavorite : "用户收藏"
    User ||--o{ UserAppUsage : "应用使用"
    User ||--o{ UserTag : "用户标签"
    User ||--o{ Conversation : "对话记录"
    
    User {
        bigint id PK "用户ID"
        string userName UK "用户标识"
        datetime lastLogin "最后登录时间"
        boolean isActive "是否活跃"
        boolean isWhitelisted "是否白名单"
        int credit "风控分"
        string personalToken "个人令牌"
        string functionLLM "函数模型ID"
        string embeddingLLM "向量模型ID"
        boolean autoExecute "自动执行"
    }
    
    UserFavorite {
        bigint id PK "收藏ID"
        int userId FK "用户标识"
        enum favouriteType "收藏类型"
        uuid itemId "项目ID"
    }
    
    UserAppUsage {
        bigint id PK "使用记录ID"
        int userId FK "用户标识"
        uuid appId FK "应用ID"
        int usageCount "使用次数"
        datetime lastUsed "最后使用时间"
    }
    
    UserTag {
        bigint id PK "标签ID"
        int userId FK "用户标识"
        bigint tag FK "标签ID"
        int count "标签归类次数"
    }
    
    Tag {
        bigint id PK "标签ID"
        string name "标签名称"
        string description "标签描述"
    }
    
    LLMData {
        string id PK "模型ID"
        string baseUrl "API地址"
        string apiKey "API密钥"
        string modelName "模型名称"
        int maxTokens "最大Token"
        string provider "提供商"
        int ctxLength "上下文长度"
    }
```

## 核心功能

### 1. 用户管理 (UserManager)

#### 功能流程图

```mermaid
flowchart TD
    A[用户请求] --> B{操作类型}
    
    B -->|获取用户列表| C[list_user]
    B -->|获取单个用户| D[get_user]
    B -->|更新用户信息| E[update_user]
    B -->|删除用户| F[delete_user]
    
    C --> C1[查询用户总数]
    C1 --> C2[分页查询用户列表]
    C2 --> C3[返回用户列表和总数]
    
    D --> D1[根据userId查询用户]
    D1 --> D2[返回用户信息或None]
    
    E --> E1{用户是否存在}
    E1 -->|不存在| E2[创建新用户]
    E1 -->|存在| E3[更新用户字段]
    E2 --> E4[保存到数据库]
    E3 --> E5[更新lastLogin时间]
    E5 --> E4
    
    F --> F1{用户是否存在}
    F1 -->|不存在| F2[直接返回]
    F1 -->|存在| F3[删除用户记录]
    F3 --> F4[删除相关对话记录]
    
    style A fill:#e1f5fe
    style E2 fill:#fff3e0
    style E3 fill:#e8f5e8
    style F3 fill:#ffebee
```

#### 主要方法

1. **list_user(n, page)**: 分页获取用户列表
2. **get_user(user_sub)**: 根据用户标识获取用户信息
3. **update_user(user_sub, data)**: 更新用户信息，支持创建新用户
4. **delete_user(user_sub)**: 删除用户及相关数据

### 2. 用户LLM配置管理

#### LLM配置更新时序图

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Router as 用户路由
    participant LLMManager as LLM管理器
    participant DB as 数据库
    participant Pool as 向量池
    participant Embedding as 向量模型
    
    Client->>Router: PUT /api/user/llm
    Router->>LLMManager: update_user_selected_llm(user_sub, request)
    
    LLMManager->>DB: 查询用户信息
    DB-->>LLMManager: 返回用户数据
    
    alt 用户不存在
        LLMManager-->>Router: 抛出ValueError异常
        Router-->>Client: 返回500错误
    else 用户存在
        LLMManager->>DB: 更新用户的functionLLM和embeddingLLM
        DB-->>LLMManager: 更新成功
        
        alt embedding模型发生变化
            LLMManager->>LLMManager: 获取新embedding模型配置
            LLMManager->>Embedding: 创建Embedding实例
            Embedding->>Embedding: 初始化模型
            LLMManager->>Pool: 设置新的向量模型
            Pool->>Pool: 触发向量化过程
        end
        
        LLMManager-->>Router: 更新完成
        Router-->>Client: 返回成功响应
    end
```

Note: 该流程不会校验 Function LLM 是否存在；当新的 embedding LLM 未找到时，系统仅记录错误日志，接口仍返回成功。

#### 核心逻辑

1. **模型验证**: 当前实现不会主动校验 Function LLM/Embedding LLM 是否存在；仅在后续向量化阶段尝试按 ID 查询模型
2. **数据更新**: 将请求中的 `functionLLM`、`embeddingLLM` 直接写入用户表
3. **向量化处理**: 当 embedding 模型发生变化时尝试初始化新模型并触发向量化；若模型缺失将记录错误但不回滚已保存的字段

### 3. 用户标签管理

#### 用户标签获取流程

```mermaid
flowchart TD
    A[客户端请求] --> B[GET /api/user/tag]
    B --> C[UserTagManager.get_user_domain_by_user_sub_and_topk]
    
    C --> D[查询用户标签记录]
    D --> E{是否有topk限制}
    E -->|是| F[按count降序排列，限制topk条]
    E -->|否| G[按count降序排列，返回全部]
    
    F --> H[遍历用户标签记录]
    G --> H
    H --> I[根据tag ID查询标签详情]
    I --> J[构建UserTagInfo对象]
    J --> K[返回标签列表]
    
    style A fill:#e1f5fe
    style K fill:#e8f5e8
```

#### 标签更新流程

```mermaid
flowchart TD
    A[标签更新请求] --> B[update_user_domain_by_user_sub_and_domain_name]
    B --> C[根据domain_name查询Tag]
    
    C --> D{Tag是否存在}
    D -->|不存在| E[抛出ValueError异常]
    D -->|存在| F[查询用户标签记录]
    
    F --> G{用户标签记录是否存在}
    G -->|不存在| H[创建新的UserTag记录]
    G -->|存在| I[增加count计数]
    
    H --> J[保存到数据库]
    I --> J
    J --> K[更新完成]
    
    style E fill:#ffebee
    style K fill:#e8f5e8
```

## API接口设计

### 接口列表

| 方法 | 路径 | 功能 | 描述 |
|------|------|------|------|
| POST | `/api/user/user` | 更新用户信息 | 更新当前登录用户的基本信息 |
| GET | `/api/user` | 获取用户列表 | 分页获取除当前用户外的所有用户 |
| PUT | `/api/user/llm` | 更新用户LLM配置 | 更新用户选择的Function和Embedding模型 |
| GET | `/api/user/tag` | 获取用户标签 | 获取用户最常涉及的领域标签 |

### 请求响应结构

#### 更新用户信息请求

```json
{
  "userName": "用户名",
  "autoExecute": false,
  "agreementConfirmed": true,
  "lastLogin": "2024-01-01T00:00:00Z"
}
```

#### 更新LLM配置请求

```json
{
  "functionLLM": "function-model-id",
  "embeddingLLM": "embedding-model-id"
}
```

#### 用户列表响应

```json
{
  "code": 200,
  "message": "用户数据详细信息获取成功",
  "result": {
    "total": 100,
    "userInfoList": [
      {
        "userId": "123",
        "userName": "张三"
      }
    ]
  }
}
```

## 数据流转图

```mermaid
graph LR
    A[客户端请求] --> B[路由层]
    B --> C[依赖验证]
    C --> D[服务层]
    D --> E[数据模型层]
    E --> F[数据库]
    
    F --> E
    E --> D
    D --> B
    B --> A
    
    subgraph "路由层"
        B1[用户路由]
        B2[会话验证]
        B3[令牌验证]
    end
    
    subgraph "服务层"
        D1[UserManager]
        D2[LLMManager]
        D3[UserTagManager]
        D4[PersonalTokenManager]
    end
    
    subgraph "数据层"
        E1[User模型]
        E2[UserTag模型]
        E3[UserFavorite模型]
        E4[UserAppUsage模型]
    end
    
    style A fill:#e1f5fe
    style F fill:#e8f5e8
```

## 安全机制

### 1. 数据隔离

- 用户只能访问和修改自己的数据
- 用户列表接口排除当前用户，避免自我操作

### 2. 数据完整性

- 用户删除时自动清理相关对话记录
- LLM配置更新时验证模型存在性
- 标签更新时验证标签有效性

## 错误处理

### 常见错误场景

1. **用户不存在**: 返回404状态码
2. **LLM模型不存在**: 返回500状态码，包含错误信息
3. **标签不存在**: 返回500状态码
4. **权限不足**: 返回403状态码
5. **数据验证失败**: 返回400状态码

### 错误响应格式

```json
{
  "code": 500,
  "message": "具体错误信息",
  "result": null
}
```
