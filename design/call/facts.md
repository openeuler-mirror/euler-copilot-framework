# Facts模块文档

## 概述

Facts模块是一个用于从对话上下文和文档片段中提取事实信息的工具。该模块通过分析用户与助手的对话内容，提取关键事实信息并生成用户画像标签，为推荐系统提供数据支持。

## 模块架构

```mermaid
graph TB
    A[FactsCall] --> B[FactsInput]
    A --> C[FactsOutput]
    A --> D[CoreCall基类]
    
    B --> E[用户ID]
    B --> F[对话消息]
    
    C --> G[提取的事实]
    C --> H[领域标签]
    
    D --> I[LLM调用]
    D --> J[模板渲染]
    
    A --> K[FactsGen]
    A --> L[DomainGen]
    
    K --> M[事实列表]
    L --> N[关键词列表]
    
    A --> O[UserTagManager]
    O --> P[用户画像更新]
```

## 核心组件

### 1. FactsCall类

继承自`CoreCall`基类，是facts模块的核心实现类。

**主要属性：**

- `answer: str` - 用户输入的回答内容
- `input_model: FactsInput` - 输入数据模型
- `output_model: FactsOutput` - 输出数据模型

**核心方法：**

- `info()` - 返回模块的名称和描述（支持中英文）
- `instance()` - 创建模块实例
- `_init()` - 初始化模块，组装输入数据
- `_exec()` - 执行事实提取逻辑
- `exec()` - 公共执行接口，处理输出格式

### 2. 数据结构

```mermaid
classDiagram
    class FactsInput {
        +str user_id
        +list~dict~ message
    }

    class FactsOutput {
        +list~str~ facts
        +list~str~ domain
    }

    class FactsGen {
        +list~str~ facts
    }

    class DomainGen {
        +list~str~ keywords
    }

    FactsGen -- FactsOutput : 生成
    DomainGen -- FactsOutput : 生成

    note for FactsInput "用户ID和对话消息列表"
    note for FactsOutput "包含提取的事实和领域标签"
    note for FactsGen "LLM生成的事实条目"
    note for DomainGen "LLM生成的关键词标签"
```

### 3. 提示词模板

#### 事实提取提示词 (FACTS_PROMPT)

从对话中提取关键信息并组织成独特的事实条目：

- **关注信息类型**：实体、偏好、关系、动作
- **提取要求**：准确、清晰、简洁（少于30字）
- **输出格式**：JSON格式的事实列表
- **语言支持**：中文/英文双语模板

#### 领域提取提示词 (DOMAIN_PROMPT)

提取推荐系统所需的关键词标签：

- **包含内容**：实体名词、技术术语、时间范围、地点、产品等
- **标签要求**：精简、不重复、不超过10字
- **输出格式**：JSON格式的关键词列表
- **语言支持**：中文/英文双语模板

## 执行流程

```mermaid
sequenceDiagram
    participant E as StepExecutor
    participant F as FactsCall
    participant L as LLM
    participant U as UserTagManager
    participant D as Database
    
    E->>F: 创建实例
    F->>F: 初始化输入数据
    F->>L: 调用事实提取
    L-->>F: 返回事实列表
    F->>L: 调用领域提取
    L-->>F: 返回关键词列表
    F->>U: 更新用户画像
    U->>D: 保存标签数据
    F-->>E: 返回提取结果
```

## 处理逻辑

```mermaid
flowchart TD
    A[开始] --> B[接收对话消息]
    B --> C[创建Jinja2环境]
    C --> D[渲染事实提取提示词]
    D --> E[调用LLM提取事实]
    E --> F[验证FactsGen结果]
    F --> G[渲染领域提取提示词]
    G --> H[调用LLM提取关键词]
    H --> I[验证DomainGen结果]
    I --> J[更新用户标签]
    J --> K[组装输出数据]
    K --> L[返回结果]
    L --> M[结束]
    
    E --> N[LLM错误处理]
    H --> O[LLM错误处理]
    N --> M
    O --> M
```

## 数据流图

```mermaid
graph LR
    A[用户对话] --> B[FactsInput]
    B --> C[消息处理]
    C --> D[事实提取LLM]
    C --> E[领域提取LLM]
    
    D --> F[FactsGen]
    E --> G[DomainGen]
    
    F --> H[事实列表]
    G --> I[关键词列表]
    
    H --> J[FactsOutput]
    I --> J
    I --> K[UserTagManager]
    
    K --> L[用户画像更新]
    J --> M[任务运行时]
    
    subgraph "数据库"
        N[Tag表]
        O[UserTag表]
    end
    
    K --> N
    K --> O
```

## 用户画像更新机制

```mermaid
graph TB
    A[提取关键词] --> B[查找Tag表]
    B --> C{标签存在?}
    C -->|是| D[查找UserTag记录]
    C -->|否| E[记录错误日志]
    
    D --> F{用户标签记录存在?}
    F -->|是| G[增加计数+1]
    F -->|否| H[创建新记录count=1]
    
    G --> I[更新数据库]
    H --> I
    E --> J[跳过该标签]
    
    I --> K[完成]
    J --> K
```

## 配置和依赖

### 依赖组件

- `CoreCall` - 基础调用框架(详见[core.md](core.md))
- `UserTagManager` - 用户标签管理服务
- `LLM` - 大语言模型服务
- `Jinja2` - 模板渲染引擎

### 配置参数

- `language` - 语言类型（中文/英文）
- `autoescape` - 模板自动转义（false）
- `trim_blocks` - 去除块空白（true）
- `lstrip_blocks` - 去除行空白（true）

## 使用示例

### 输入示例

```python
input_data = {
    "user_id": "user123",
    "message": [
        {"role": "user", "content": "北京天气如何？"},
        {"role": "assistant", "content": "北京今天晴天，温度25度。"}
    ]
}
```

### 输出示例

```python
output = {
    "facts": ["北京今天天气晴朗", "北京今日温度25度"],
    "domain": ["北京", "天气"]
}
```

## 错误处理

1. **LLM调用失败** - 记录错误日志，返回空结果
2. **数据验证失败** - 抛出类型错误异常
3. **标签不存在** - 记录错误日志，跳过该标签
4. **数据库操作失败** - 抛出相应异常

## 性能考虑

- 使用异步生成器模式，支持流式输出
- 模板渲染缓存，提高重复调用效率
- 批量数据库操作，减少I/O开销
- 错误恢复机制，保证系统稳定性

## 扩展性

- 支持多语言提示词模板
- 可配置的事实提取规则
- 可扩展的用户画像维度
- 支持自定义输出格式
