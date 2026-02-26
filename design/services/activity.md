# Activity模块设计文档

## 概述

Activity 模块是 openEuler Intelligence 框架中的用户活动控制系统，负责管理系统的全局并发限制和用户限流。该模块实现了单用户滑动窗口限流（仅在检测阶段）和全局并发任务限制，确保系统在高负载情况下的稳定性和公平性。

**核心理念**: 全局并发限制，同时最多有 n 个任务在执行（与用户无关）。

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
  - `timestamp`: 活动时间戳 (DateTime, UTC时区)
- **索引**: userId 字段建立索引，提高查询效率
- **说明**: 记录用户的活动任务，用于实现滑动窗口限流和全局并发控制

### 相关实体

- **User**: 用户基础信息表 (`framework_user`)
- **Session**: 会话管理表 (`framework_session`)

## 配置常量

- `MAX_CONCURRENT_TASKS`: 全局同时运行任务上限 (默认: 30)
- `SLIDE_WINDOW_TIME`: 滑动窗口时间 (默认: 15秒)
- `SLIDE_WINDOW_QUESTION_COUNT`: 滑动窗口内最大请求数 (默认: 5)

## 服务层

### Activity类

**定义位置**: `apps.services.activity.Activity`

**依赖模块**:

- `apps.common.postgres`: PostgreSQL 数据库连接管理
- `apps.constants`: 配置常量（MAX_CONCURRENT_TASKS, SLIDE_WINDOW_TIME, SLIDE_WINDOW_QUESTION_COUNT）
- `apps.exceptions`: ActivityError 异常类
- `apps.models`: SessionActivity 数据模型

**类描述**: 活动控制服务，实现全局并发限制，同时最多有 n 个任务在执行（与用户无关）

#### 静态方法

- `can_active(user_id)`: 判断系统是否达到全局并发上限
  - **参数**: `user_id` - 用户实体ID（兼容现有接口签名）
  - **返回**: 达到并发上限返回 `False`，否则 `True`
  - **逻辑**:
    1. 单用户滑动窗口限流：统计该用户在 `[now - SLIDE_WINDOW_TIME, now]` 时间窗口内的请求数（使用 `timestamp >= time - timedelta(seconds=SLIDE_WINDOW_TIME)` 和 `timestamp <= time`），若 count >= `SLIDE_WINDOW_QUESTION_COUNT` 则返回 `False`
    2. 全局并发检查：统计当前所有活跃任务数，若 >= `MAX_CONCURRENT_TASKS` 则返回 `False`
    3. 两项检查都通过则返回 `True`

- `set_active(user_id)`: 设置活跃标识，当未超过全局并发上限时登记一个活动任务
  - **参数**: `user_id` - 用户实体ID
  - **逻辑**:
    1. 并发上限校验：统计当前活跃任务数，若 >= `MAX_CONCURRENT_TASKS` 则抛出 `ActivityError("系统并发已达上限")`
    2. 使用 `session.add()` 添加新的 `SessionActivity` 记录，包含 userId 和当前时间戳（UTC时区）
    3. 提交数据库事务
  - **注意**: 每次调用都会新增一条记录（不是更新已有记录）

- `is_active(user_id)`: 判断用户是否仍然活跃（即是否有活动记录）
  - **参数**: `user_id` - 用户实体ID
  - **返回**: 统计该用户的活动记录数量，返回 count > 0
  - **用途**: 检查用户当前是否有正在执行的任务

- `remove_active(user_id)`: 释放一个活动任务名额（按用户标识清除对应记录）
  - **参数**: `user_id` - 用户实体ID
  - **逻辑**:
    1. 使用 `DELETE FROM framework_session_activity WHERE userId = ?` 删除该用户的所有 SessionActivity 记录
    2. 提交数据库事务
  - **注意**: 会删除该用户的所有活动记录，释放对应的任务名额

> **设计说明**
>
> - `can_active` 负责两层限流检查：用户级（滑动窗口）+ 系统级（全局并发）
> - `set_active` 每次调用都新增一条记录，同一用户可能有多条活动记录（对应多个并发任务）
> - `remove_active` 会删除用户的所有活动记录，适用于清理该用户的所有任务
> - 时间戳使用 UTC 时区，确保跨时区一致性
> - 滑动窗口使用闭区间 `[now - SLIDE_WINDOW_TIME, now]` 进行时间范围查询

## 时序图

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant Router as 路由层
    participant Activity as Activity服务
    participant DB as 数据库

    Note over Client, DB: 用户请求处理流程
    Client->>Router: 发起请求
    Router->>Activity: can_active(user_id)
    
    Note over Activity, DB: 滑动窗口限流检查
    Activity->>DB: SELECT COUNT(*) FROM framework_session_activity<br/>WHERE userId=? AND timestamp BETWEEN (now-15s) AND now
    DB-->>Activity: 返回用户窗口内请求数
    Activity->>Activity: 检查是否 >= SLIDE_WINDOW_QUESTION_COUNT

    alt 用户请求数超限
        Activity-->>Router: 返回False (限流)
        Router-->>Client: 返回429错误
    else 用户请求数正常
        Note over Activity, DB: 全局并发检查
        Activity->>DB: SELECT COUNT(*) FROM framework_session_activity
        DB-->>Activity: 返回当前活跃任务数
        Activity->>Activity: 检查是否 >= MAX_CONCURRENT_TASKS

        alt 全局并发超限
            Activity-->>Router: 返回False (限流)
            Router-->>Client: 返回429错误
        else 系统可处理
            Activity-->>Router: 返回True (允许)
            Router->>Activity: set_active(user_id)
            
            Note over Activity, DB: 设置活动状态
            Activity->>DB: SELECT COUNT(*) FROM framework_session_activity
            DB-->>Activity: 返回当前活跃任务数
            Activity->>Activity: 检查是否 >= MAX_CONCURRENT_TASKS

            alt 并发超限
                Activity-->>Router: 抛出ActivityError
                Router-->>Client: 返回503错误
            else 系统仍可处理
                Activity->>DB: INSERT INTO framework_session_activity<br/>(userId, timestamp)
                DB-->>Activity: 插入成功
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
    A[用户请求] --> B[Activity.can_active检查]

    B --> C{滑动窗口限流检查}
    C -->|超过限制| D[返回False]
    C -->|未超过| E{全局并发检查}

    E -->|超过限制| D
    E -->|未超过| F[返回True]

    F --> G[Activity.set_active]
    
    G --> H{并发检查}
    H -->|检查失败| I[抛出ActivityError]
    H -->|检查通过| J[插入活动记录]

    J --> K[处理用户请求]
    K --> L[请求完成]
    L --> M[Activity.remove_active]
    M --> N[删除活动记录]
    N --> O[释放资源]

    D --> P[返回429错误]
    I --> Q[返回503错误]
    O --> R[请求处理完成]
    
    style A fill:#e1f5fe
    style R fill:#c8e6c9
    style P fill:#ffcdd2
    style Q fill:#ffcdd2
    style D fill:#fff3e0
    style I fill:#fff3e0
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
        L --> M{>= 上限?}
        M -->|是| O[抛出ActivityError]
        M -->|否| N[插入新记录]
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

- **定义位置**: `apps.exceptions.ActivityError`
- **触发条件**: 当系统并发已达上限时调用 `set_active` 方法
- **错误信息**: `"系统并发已达上限"`
- **处理方式**: 向上层抛出异常，由路由层捕获并返回适当的 HTTP 状态码（如 503 Service Unavailable）
- **注意**: `can_active` 方法不会抛出异常，只返回布尔值；只有 `set_active` 方法会抛出此异常

## 安全考虑

1. **双重限流保护**:
   - 用户级别限流：滑动窗口机制防止单个用户在短时间内大量请求
   - 系统级别限流：全局并发控制防止系统整体过载

2. **时间窗口控制**:
   - 使用闭区间 `[now - SLIDE_WINDOW_TIME, now]` 的滑动窗口
   - 默认15秒窗口，防止用户短时间内超过5次请求

3. **并发限制**:
   - 全局最多30个并发任务（可配置）
   - `can_active` 和 `set_active` 都会进行并发检查，双重保障

4. **资源及时释放**:
   - 使用 try-finally 模式确保资源释放
   - `remove_active` 删除所有用户活动记录

5. **UTC时区统一**:
   - 所有时间戳使用 UTC 时区（`datetime.now(tz=UTC)` 和 `datetime.now(UTC)`）
   - 避免跨时区的时间计算问题

## 性能优化

1. **数据库索引**:
   - userId 字段建立索引，提高滑动窗口查询效率
   - id 字段作为主键，优化 COUNT 操作

2. **异步操作**:
   - 所有数据库操作使用 async/await 异步方式
   - 使用 SQLAlchemy 异步会话（`postgres.session()`）

3. **查询优化**:
   - 使用 `func.count()` 进行高效计数
   - 滑动窗口查询使用时间范围索引
   - `scalars().one()` 获取单个标量结果

4. **连接池管理**:
   - 使用 `async with postgres.session()` 上下文管理器
   - 自动管理数据库连接的获取和释放

5. **事务控制**:
   - 写操作（`set_active`, `remove_active`）使用显式 `commit()`
   - 读操作（`can_active`, `is_active`）无需提交

6. **批量清理建议**:
   - 可考虑定期清理过期的活动记录（超过 SLIDE_WINDOW_TIME）
   - 防止 SessionActivity 表无限增长

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

配置项定义在 `apps.constants` 模块中：

```python
# 活动控制配置（位于 apps/constants.py）
MAX_CONCURRENT_TASKS = 30        # 全局并发任务上限
SLIDE_WINDOW_TIME = 15           # 滑动窗口时间(秒)
SLIDE_WINDOW_QUESTION_COUNT = 5  # 窗口内最大请求数
```

**配置说明**:

- `MAX_CONCURRENT_TASKS`: 系统全局同时运行的最大任务数，超过此数量将拒绝新任务
- `SLIDE_WINDOW_TIME`: 滑动窗口的时间长度（单位：秒），默认15秒
- `SLIDE_WINDOW_QUESTION_COUNT`: 在滑动窗口时间内，单个用户允许的最大请求数

## 使用示例

```python
from apps.services.activity import Activity
from apps.exceptions import ActivityError
from fastapi import HTTPException

# 典型使用流程
async def handle_user_request(user_id: str):
    """处理用户请求的典型流程"""

    # 1. 检查系统是否可以接受新任务
    if not await Activity.can_active(user_id):
        # 返回 429 Too Many Requests（请求过于频繁或系统繁忙）
        raise HTTPException(status_code=429, detail="请求过于频繁或系统繁忙")

    # 2. 设置活动状态，登记任务
    try:
        await Activity.set_active(user_id)
    except ActivityError as e:
        # 返回 503 Service Unavailable（系统并发已达上限）
        raise HTTPException(status_code=503, detail=str(e))

    try:
        # 3. 处理业务逻辑
        result = await process_user_task(user_id)
        return result
    finally:
        # 4. 清理活动状态（无论成功或失败都要清理）
        await Activity.remove_active(user_id)


# 检查用户是否有活跃任务
async def check_user_activity(user_id: str) -> bool:
    """检查用户是否有正在执行的任务"""
    return await Activity.is_active(user_id)
```

**使用注意事项**:

1. **必须使用 finally**: 确保在任何情况下（成功/失败/异常）都调用 `remove_active` 清理活动记录
2. **先 can_active 后 set_active**: 推荐先调用 `can_active` 检查，再调用 `set_active` 登记
3. **异常处理**: `can_active` 返回布尔值，`set_active` 可能抛出 `ActivityError`
4. **时区一致**: 所有时间戳使用 UTC 时区，确保跨时区一致性
