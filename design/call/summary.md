# Summary工具模块文档

## 概述

Summary工具是一个用于理解对话上下文的Call，它通过分析对话记录和事实条目，生成背景总结，为后续Flow的上下文理解提供支持。

## 核心组件

### 1. Summary类

Summary工具的核心实现类，继承自`CoreCall`基类。

### 2. 主要属性

| 属性名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `context` | ExecutorBackground | - | 对话上下文信息，包含对话记录、关键事实等 |

**主要方法：**

- `info()`: 返回工具的多语言名称和描述
- `instance()`: 创建工具实例
- `_init()`: 初始化工具输入
- `_exec()`: 执行总结生成逻辑

### 3. 数据结构

Summary工具涉及多个数据模型，它们之间的关系如下：

```mermaid
classDiagram
    class SummaryOutput {
        +summary: str
    }

    class ExecutorBackground {
        +num: int
        +conversation: list[dict[str, str]]
        +facts: list[str]
    }

    class Summary {
        +context: ExecutorBackground
        +info() CallInfo
        +instance() Self
        +_init() DataBase
        +_exec() AsyncGenerator
        +exec() AsyncGenerator
    }

    Summary --> ExecutorBackground : 使用
    Summary --> SummaryOutput : 输出

    note for Summary "继承自CoreCall基类<br/>输入使用DataBase<br/>详见core.md"
    note for SummaryOutput "继承自DataBase<br/>详见core.md"
    note for ExecutorBackground "详见core.md"
```

#### 数据模型说明

- **SummaryOutput**: 包含总结内容的输出模型(继承自DataBase，详见[core.md](core.md))
- **ExecutorBackground**: 执行器背景信息，包含对话记录和关键事实(详见[core.md](core.md))

#### 数据流转关系

```mermaid
graph LR
    A[ExecutorBackground] --> B[Summary工具]
    B --> C[SummaryOutput]
    C --> D[task.runtime.reasoning]
    
    subgraph "输入数据"
        A1[num: 对话记录数量]
        A2[conversation: 对话记录列表]
        A3[facts: 关键事实列表]
    end
    
    subgraph "处理过程"
        B1[模板渲染]
        B2[LLM推理]
    end
    
    subgraph "输出数据"
        C1[summary: 总结内容]
    end
    
    A1 --> B1
    A2 --> B1
    A3 --> B1
    B1 --> B2
    B2 --> C1
    C1 --> D
```

### 4. 提示词模板

Summary工具使用Jinja2模板引擎生成提示词，支持中英文两种语言。模板设计遵循以下原则：

- **结构化指令**：使用XML标签清晰分隔不同部分
- **动态内容渲染**：通过Jinja2循环语法动态生成对话记录
- **多语言适配**：根据系统语言自动选择合适的模板
- **输出格式控制**：明确指定输出要求和限制

Summary工具提供中英文两种语言的提示词模板，两种模板在结构和功能上保持一致，仅在语言表述上有所差异。模板设计包含以下核心要素：

1. **任务说明**：明确要求生成三句话背景总结，用于后续对话的上下文理解
2. **质量要求**：强调突出重要信息点（时间、地点、人物、事件等），确保信息准确性，不得编造信息
3. **格式约束**：限制输出长度（少于3句话，少于300个字），不包含XML标签
4. **数据源标识**：清晰标记对话记录和关键事实的来源，使用XML标签进行结构化组织

## 工作流程

```mermaid
graph TD
    A[开始] --> B[接收ExecutorBackground上下文]
    B --> C[创建Jinja2模板环境]
    C --> D[根据语言选择提示词模板]
    D --> E[渲染模板生成完整提示词]
    E --> F[调用LLM生成总结]
    F --> G[流式输出总结内容]
    G --> H[将总结保存到task.runtime.reasoning]
    H --> I[结束]
    
    subgraph "数据流"
        J[conversation: 对话记录]
        K[facts: 关键事实]
        L[language: 语言类型]
    end
    
    J --> E
    K --> E
    L --> D
```

## 执行时序图

```mermaid
sequenceDiagram
    participant E as StepExecutor
    participant S as Summary
    participant T as Jinja2Template
    participant L as LLM
    participant R as Runtime
    
    E->>S: instance(executor, node)
    S->>S: _set_input(executor)
    S->>S: _init(call_vars)
    
    E->>S: exec(executor, input_data)
    S->>S: _exec(input_data)
    S->>T: 创建SandboxedEnvironment
    S->>T: 选择语言模板
    S->>T: render(conversation, facts)
    T-->>S: 生成完整提示词
    
    S->>L: 调用LLM生成总结
    L-->>S: 流式返回总结内容
    S->>R: 保存到task.runtime.reasoning
    S-->>E: 返回CallOutputChunk
```

## 数据流图

```mermaid
graph LR
    subgraph "输入数据"
        A[ExecutorBackground]
        A1[conversation: 对话记录]
        A2[facts: 关键事实]
        A3[num: 最大记录数]
    end
    
    subgraph "处理过程"
        B[Jinja2模板渲染]
        C[LLM推理生成]
    end
    
    subgraph "输出数据"
        D[SummaryOutput]
        D1[summary: 总结内容]
        E[task.runtime.reasoning]
    end
    
    A1 --> B
    A2 --> B
    A3 --> B
    B --> C
    C --> D1
    D1 --> E
```

## 使用示例

Summary工具是系统内置的隐藏工具，不可由用户直接使用。

### 上下文数据示例

```python
# ExecutorBackground数据结构示例
context = ExecutorBackground(
    num=10,
    conversation=[
        {"role": "user", "content": "你好，我想了解Python编程"},
        {"role": "assistant", "content": "当然可以！Python是一门很受欢迎的编程语言..."},
        {"role": "user", "content": "能给我一些学习建议吗？"}
    ],
    facts=[
        "用户对Python编程感兴趣",
        "用户希望获得学习建议",
        "对话发生在2024年"
    ]
)
```

## 配置参数

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `context` | ExecutorBackground | - | 对话上下文信息 |
| `to_user` | bool | False | 是否将输出返回给用户 |
| `enable_filling` | bool | False | 是否需要进行自动参数填充 |

## 错误处理

Summary工具包含以下错误处理机制：

1. **输出格式验证**：检查LLM输出是否为字符串格式
2. **模板渲染错误**：Jinja2模板渲染异常处理
3. **LLM调用异常**：大模型调用失败处理
