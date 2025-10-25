# Activity模块设计文档

## 概述

Activity 模块是 openEuler Intelligence 框架中的用户活动控制系统，负责管理系统的并发限制和用户限流。该模块实现了单用户滑动窗口限流和全局并发任务限制，确保系统在高负载情况下的稳定性和公平性。

## 核心功能

- **全局并发控制**: 限制系统同时执行的任务数量，防止系统过载
- **单用户限流**: 基于滑动窗口的用户请求频率限制（当前仅在活动检测阶段执行）
- **活动状态管理**: 跟踪和管理用户活动状态
- **资源保护**: 通过限流机制保护系统资源

## 数据模型

### SessionActivity实体

- **表名**: `framework_session_activity`
- **主键**: `id` (BigInteger, 自增)
- **字段**:
  - `userId`: 用户标识 (String(50), 外键关联framework_user.userId)
  - `timestamp`: 活动时间戳 (DateTime, 时区感知)

### 相关实体

- **User**: 用户基础信息表 (`framework_user`)
- **Session**: 会话管理表 (`framework_session`)

## 配置常量

- `MAX_CONCURRENT_TASKS`: 全局同时运行任务上限 (默认: 30)
- `SLIDE_WINDOW_TIME`: 滑动窗口时间 (默认: 15秒)
- `SLIDE_WINDOW_QUESTION_COUNT`: 滑动窗口内最大请求数 (默认: 5)

## 服务层

### Activity类

#### 静态方法

- `is_active(user_id)`: 先按用户滑动窗口统计，再按全局并发统计，达到任一阈值即返回 `True`
- `set_active(user_id)`: 在未超过全局并发上限时登记一个活动任务，内部使用 SQLAlchemy `merge` 以 userId 为键写入最新时间戳
- `remove_active(user_id)`: 移除用户活动状态

> **注意**
> 当前实现仅在 `is_active` 阶段执行滑动窗口校验；`set_active` 只进行一次全局并发计数后写入数据库。

## 时序图

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Router as 路由层
    participant Activity as Activity服务
    participant DB as 数据库

    Note over Client, DB: 用户请求处理流程
    Client->>Router: 发起请求
    Router->>Activity: is_active(user_id)
    
    Note over Activity, DB: 滑动窗口限流检查
    Activity->>DB: SELECT COUNT(*) FROM framework_session_activity<br/>WHERE userId=? AND timestamp >= ?
    DB-->>Activity: 返回用户窗口内请求数
    Activity->>Activity: 检查是否超过SLIDE_WINDOW_QUESTION_COUNT
    
    alt 用户请求数超限
        Activity-->>Router: 返回True (限流)
        Router-->>Client: 返回429错误
    else 用户请求数正常
        Note over Activity, DB: 全局并发检查
        Activity->>DB: SELECT COUNT(*) FROM framework_session_activity
        DB-->>Activity: 返回当前活跃任务数
        Activity->>Activity: 检查是否超过MAX_CONCURRENT_TASKS
        
        alt 全局并发超限
            Activity-->>Router: 返回True (限流)
            Router-->>Client: 返回429错误
        else 系统可处理
            Activity-->>Router: 返回False (允许)
            Router->>Activity: set_active(user_id)
            
            Note over Activity, DB: 设置活动状态
            Activity->>DB: SELECT COUNT(*) FROM framework_session_activity
            DB-->>Activity: 返回当前活跃任务数
            Activity->>Activity: 检查是否超过MAX_CONCURRENT_TASKS
            
            alt 并发超限
                Activity-->>Router: 抛出ActivityError
                Router-->>Client: 返回503错误
            else 系统仍可处理
                Activity->>DB: MERGE INTO framework_session_activity<br/>(userId, timestamp)
                DB-->>Activity: 插入或更新成功
                Activity-->>Router: 设置成功
                Router-->>Client: 处理请求
                
                Note over Client, DB: 请求完成后清理
                Client->>Router: 请求完成
                Router->>Activity: remove_active(user_id)
                Activity->>DB: DELETE FROM framework_session_activity<br/>WHERE userId=?
                DB-->>Activity: 删除成功
                Activity-->>Router: 清理完成
            end
        end
    end
```

## ER图

```mermaid
erDiagram
    User ||--o{ SessionActivity : "用户产生活动"
    
    User {
        BigInteger id PK
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
    
    SessionActivity {
        BigInteger id PK
        string userId FK "用户标识"
        datetime timestamp "活动时间戳"
    }
    
    Session {
        string id PK "会话ID"
        string userId FK "用户标识"
        string ip "IP地址"
        string pluginId "插件ID"
        string token "Token信息"
        datetime validUntil "有效期"
        enum sessionType "会话类型"
    }
```

## 流程图

```mermaid
flowchart TD
    A[用户请求] --> B[Activity.is_active检查]
    
    B --> C{滑动窗口限流检查}
    C -->|超过限制| D[返回限流状态]
    C -->|未超过| E{全局并发检查}
    
    E -->|超过限制| D
    E -->|未超过| F[Activity.set_active]
    
    F --> G{并发检查}
    G -->|检查失败| H[抛出ActivityError]
    G -->|检查通过| I[插入/更新活动记录]
    
    I --> J[处理用户请求]
    J --> K[请求完成]
    K --> L[Activity.remove_active]
    L --> M[删除活动记录]
    M --> N[释放资源]
    
    D --> O[返回429错误]
    H --> P[返回503错误]
    N --> Q[请求处理完成]
    
    style A fill:#e1f5fe
    style Q fill:#c8e6c9
    style O fill:#ffcdd2
    style P fill:#ffcdd2
    style D fill:#fff3e0
    style H fill:#fff3e0
```

## 限流机制详解

```mermaid
flowchart LR
    subgraph "滑动窗口限流"
        A[用户请求] --> B[检查15秒内请求数]
        B --> C{请求数 >= 5?}
        C -->|是| D[限流]
        C -->|否| E[通过]
    end
    
    subgraph "全局并发限流"
        F[系统请求] --> G[检查当前活跃任务数]
        G --> H{任务数 >= 30?}
        H -->|是| I[限流]
        H -->|否| J[通过]
    end
    
    subgraph "登记活跃任务"
        K[set_active调用] --> L[统计当前活跃任务数]
        L --> M{超过上限?}
        M -->|是| O[抛出异常]
        M -->|否| N[插入/更新记录]
    end
    
    E --> F
    J --> K
    
    style D fill:#ffcdd2
    style I fill:#ffcdd2
    style O fill:#ffcdd2
    style E fill:#c8e6c9
    style J fill:#c8e6c9
    style N fill:#c8e6c9
```

## 数据流转图

```mermaid
flowchart LR
    subgraph "请求层"
        A[用户请求]
        B[API调用]
    end
    
    subgraph "控制层"
        C[Activity服务]
        D[限流检查]
        E[并发控制]
    end
    
    subgraph "数据层"
        F[PostgreSQL]
        G[SessionActivity表]
        H[User表]
    end
    
    subgraph "业务层"
        I[业务处理]
        J[资源释放]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    F --> H
    
    G -.->|活动记录| C
    H -.->|用户信息| C
    C -.->|限流结果| B
    B -.->|处理请求| I
    I -.->|完成通知| J
    J -.->|清理活动| C
    
    style A fill:#e3f2fd
    style C fill:#f3e5f5
    style F fill:#e8f5e8
    style I fill:#fff8e1
```

## 异常处理

### ActivityError异常

- **触发条件**: 当系统并发已达上限时调用`set_active`方法
- **错误信息**: "系统并发已达上限"
- **处理方式**: 向上层抛出异常，由路由层处理

## 安全考虑

1. **双重限流保护**: 用户级别和系统级别的双重限流机制
2. **时间窗口控制**: 滑动窗口防止用户短时间内大量请求
3. **并发限制**: 全局并发控制防止系统过载
4. **资源及时释放**: 请求完成后及时清理活动记录

## 性能优化

1. **数据库索引**: userId字段建立索引，提高查询效率
2. **异步操作**: 所有数据库操作使用异步方式
3. **连接池管理**: 使用数据库连接池管理连接
4. **批量清理**: 可考虑定期清理过期的活动记录

## 监控指标

1. **并发任务数**: 实时监控当前活跃任务数量
2. **限流触发次数**: 统计限流机制触发频率
3. **用户请求频率**: 监控用户请求模式
4. **系统响应时间**: 监控限流对系统性能的影响

## 扩展性

1. **动态配置**: 支持运行时调整限流参数
2. **多级限流**: 可扩展支持更复杂的限流策略
3. **限流策略**: 可扩展支持令牌桶、漏桶等算法
4. **分布式限流**: 可扩展支持分布式环境下的限流控制

## 配置说明

```toml
# 活动控制配置
MAX_CONCURRENT_TASKS = 30        # 全局并发任务上限
SLIDE_WINDOW_TIME = 15           # 滑动窗口时间(秒)
SLIDE_WINDOW_QUESTION_COUNT = 5  # 窗口内最大请求数
```

## 使用示例

```python
# 检查是否被限流
if await Activity.is_active(user_id):
    raise HTTPException(status_code=429, detail="请求过于频繁")

# 设置活动状态
try:
    await Activity.set_active(user_id)
    # 处理业务逻辑
finally:
    # 清理活动状态
    await Activity.remove_active(user_id)
```
