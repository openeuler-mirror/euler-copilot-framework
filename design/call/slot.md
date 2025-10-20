# Slot工具模块文档

## 概述

Slot工具是一个智能参数自动填充工具，它通过分析历史步骤数据、背景信息和用户问题，自动生成符合JSON Schema要求的参数对象。该工具使用JsonGenerator进行精确的剩余参数填充。

## 功能特性

- **智能参数填充**：基于历史步骤和背景信息自动填充工具参数
- **Schema验证**：支持JSON Schema验证和错误检测
- **模板化提示词**：使用Jinja2模板引擎动态生成提示词
- **结构化数据**：基于Pydantic模型进行数据验证和序列化

## 核心组件

### 1. Slot类

Slot工具的核心实现类，继承自`CoreCall`基类，负责参数自动填充的整个流程。

### 2. 主要属性

| 属性名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `data` | dict[str, Any] | {} | 当前输入数据 |
| `current_schema` | dict[str, Any] | {} | 当前JSON Schema |
| `summary` | str | "" | 背景信息总结 |
| `facts` | list[str] | [] | 事实信息列表 |
| `step_num` | int | 1 | 历史步骤数 |

### 3. 核心方法

- `info()`: 返回工具的多语言名称和描述
- `instance()`: 创建工具实例
- `_init()`: 初始化工具输入，处理历史数据和Schema
- `_exec()`: 执行参数填充逻辑
- `_llm_slot_fill()`: 使用大语言模型填充参数
- `_function_slot_fill()`: 使用JsonGenerator填充剩余参数

## 数据结构

Slot工具涉及多个数据模型，它们之间的关系如下：

```mermaid
classDiagram
    class SlotInput {
        +remaining_schema: dict
    }

    class SlotOutput {
        +slot_data: dict
        +remaining_schema: dict
    }

    class Slot {
        +data: dict
        +current_schema: dict
        +summary: str
        +facts: list
        +step_num: int
        +info() CallInfo
        +instance() Self
        +_init() SlotInput
        +_exec() AsyncGenerator
        +_llm_slot_fill() tuple
        +_function_slot_fill() dict
    }

    class SlotProcessor {
        +_validator_cls: type
        +_validator: Validator
        +_schema: dict
        +process_json() dict
        +convert_json() dict
        +check_json() dict
        +add_null_to_basic_types() dict
    }

    Slot --> SlotInput : 输入
    Slot --> SlotOutput : 输出
    Slot --> SlotProcessor : 使用
    SlotProcessor --> SlotInput : 生成remaining_schema
    SlotProcessor --> SlotOutput : 验证和转换数据

    note for Slot "继承自CoreCall基类<br/>详见core.md"
    note for SlotInput "继承自DataBase<br/>详见core.md"
    note for SlotOutput "继承自DataBase<br/>详见core.md"
```

### 数据模型说明

- **SlotInput**: 包含剩余需要填充的Schema信息(继承自DataBase，详见[core.md](core.md))
- **SlotOutput**: 包含填充后的数据和剩余Schema(继承自DataBase，详见[core.md](core.md))
- **SlotProcessor**: 参数槽处理器，负责JSON Schema验证和数据转换

### 数据流转关系

```mermaid
graph LR
    A[CallVars] --> B[Slot工具]
    B --> C[SlotProcessor]
    C --> D[SlotInput]
    D --> E[LLM填充]
    E --> F[JsonGenerator填充]
    F --> G[SlotOutput]
    
    subgraph "输入数据"
        A1[question: 用户问题]
        A2[step_data: 历史步骤数据]
        A3[current_schema: JSON Schema]
        A4[summary: 背景总结]
        A5[facts: 事实信息]
    end
    
    subgraph "处理过程"
        B1[历史数据处理]
        B2[Schema验证]
        B3[LLM推理填充]
        B4[JsonGenerator精确填充]
        B5[数据转换和验证]
    end
    
    subgraph "输出数据"
        G1[slot_data: 填充后的数据]
        G2[remaining_schema: 剩余Schema]
    end
    
    A1 --> B1
    A2 --> B1
    A3 --> B2
    A4 --> B3
    A5 --> B3
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> B5
    B5 --> G1
    B5 --> G2
```

## 提示词模板

Slot工具使用Jinja2模板引擎生成提示词，支持中英文两种语言。模板设计遵循以下原则：

### 模板设计特点

- **结构化指令**：使用XML标签清晰分隔不同部分
- **动态内容渲染**：通过Jinja2循环语法动态生成历史工具数据
- **输出格式控制**：明确指定JSON输出要求和限制

### 提示词模板结构

```mermaid
graph TD
    A[SLOT_GEN_PROMPT] --> B[instructions]
    A --> C[example]
    A --> D[context]
    A --> E[question]
    A --> F[tool_info]
    A --> G[tool_call]
    A --> H[output]
    
    B --> B1[任务说明]
    B --> B2[要求列表]
    B --> B3[输出约束]
    
    C --> C1[示例场景]
    C --> C2[工具信息]
    C --> C3[Schema结构]
    C --> C4[期望输出]
    
    D --> D1[历史总结]
    D --> D2[事实信息]
    D --> D3[工具调用历史]
    
    E --> E1[用户问题]
    
    F --> F1[工具名称]
    F --> F2[工具描述]
    
    G --> G1[JSON Schema]
    
    H --> H1[JSON对象输出]
```

### 模板核心要素

1. **任务说明**：明确要求生成符合JSON Schema的参数对象
2. **数据优先级**：用户输入 > 背景信息 > 历史数据
3. **格式约束**：严格按照JSON Schema输出，不编造字段
4. **可选字段处理**：可省略可选字段
5. **示例说明**：提供具体的使用示例

## 工作流程

Slot工具采用两阶段填充策略，确保参数填充的准确性和完整性：

```mermaid
graph TD
    A[开始] --> B[接收输入数据]
    B --> C[初始化SlotProcessor]
    C --> D[检查当前Schema]
    D --> E{是否有剩余Schema?}
    E -->|否| F[返回空结果]
    E -->|是| G[第一阶段：LLM填充]
    G --> H[解析LLM输出]
    H --> I[数据转换]
    I --> J[检查剩余Schema]
    J --> K{仍有剩余Schema?}
    K -->|否| L[输出最终结果]
    K -->|是| M[第二阶段：JsonGenerator填充]
    M --> N[数据转换]
    N --> O[最终Schema检查]
    O --> L
    L --> P[结束]
    
    subgraph "LLM填充阶段"
        G1[创建Jinja2模板]
        G2[渲染提示词]
        G3[调用LLM]
        G4[解析JSON响应]
    end
    
    subgraph "JsonGenerator填充阶段"
        M1[构建对话上下文]
        M2[调用JSON生成器]
        M3[获取结构化数据]
    end
    
    G --> G1
    G1 --> G2
    G2 --> G3
    G3 --> G4
    G4 --> H
    
    M --> M1
    M1 --> M2
    M2 --> M3
    M3 --> N
```

## 执行时序图

```mermaid
sequenceDiagram
    participant E as StepExecutor
    participant S as Slot
    participant SP as SlotProcessor
    participant T as Jinja2Template
    participant L as LLM
    participant J as JsonGenerator
    participant V as JSONValidator
    
    E->>S: instance(executor, node)
    S->>S: _set_input(executor)
    S->>S: _init(call_vars)
    S->>SP: 创建SlotProcessor(schema)
    SP->>SP: 初始化验证器
    SP->>S: 返回remaining_schema
    
    E->>S: exec(executor, input_data)
    S->>S: _exec(input_data)
    
    alt 有剩余Schema
        S->>T: 创建SandboxedEnvironment
        S->>T: 选择语言模板
        S->>T: render(工具信息, Schema, 历史数据, 总结, 问题, 事实)
        T-->>S: 生成完整提示词
        
        S->>L: 调用LLM生成参数
        L-->>S: 流式返回JSON响应
        S->>J: process_response(answer)
        J-->>S: 处理后的JSON字符串
        S->>V: json.loads(answer)
        V-->>S: 解析的JSON数据
        
        S->>SP: convert_json(slot_data)
        SP-->>S: 转换后的数据
        S->>SP: check_json(slot_data)
        SP-->>S: 剩余Schema
        
        alt 仍有剩余Schema
            S->>J: _json(messages, schema)
            J-->>S: 结构化JSON数据
            S->>SP: convert_json(slot_data)
            SP-->>S: 转换后的数据
            S->>SP: check_json(slot_data)
            SP-->>S: 最终剩余Schema
        end
    end
    
    S-->>E: 返回CallOutputChunk
```

## 核心算法

### 1. 两阶段填充策略

```mermaid
graph LR
    A[原始Schema] --> B[LLM填充阶段]
    B --> C[JsonGenerator填充阶段]
    C --> D[最终结果]

    B --> B1[生成自然语言提示词]
    B --> B2[LLM推理生成JSON]
    B --> B3[解析和验证JSON]

    C --> C1[构建结构化对话]
    C --> C2[调用JSON生成器]
    C --> C3[获取精确JSON数据]
    
    D --> D1[slot_data: 填充数据]
    D --> D2[remaining_schema: 剩余Schema]
```

### 2. Schema验证流程

```mermaid
graph TD
    A[输入JSON数据] --> B[SlotProcessor.check_json]
    B --> C[使用Draft7Validator验证]
    C --> D{验证是否通过?}
    D -->|通过| E[返回空Schema]
    D -->|失败| F[提取验证错误]
    F --> G[构建错误Schema模板]
    G --> H[生成JSON Pointer路径]
    H --> I[返回remaining_schema]
    
    subgraph "错误处理"
        F1[遍历验证错误]
        F2[提取字段路径]
        F3[构建字段Schema]
        F4[添加到required列表]
    end
    
    F --> F1
    F1 --> F2
    F2 --> F3
    F3 --> F4
    F4 --> G
```

## 使用示例

### 基本使用

Slot工具是系统内置的隐藏工具，不可由用户直接使用。

### 输出数据示例

```python
# Slot工具输出数据结构示例
slot_output = SlotOutput(
    slot_data={
        "city": "杭州",
        "date": "明天"
    },
    remaining_schema={}  # 空表示所有参数已填充完成
)
```

## 配置参数

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `data` | dict[str, Any] | {} | 当前输入数据 |
| `current_schema` | dict[str, Any] | {} | 当前JSON Schema |
| `summary` | str | "" | 背景信息总结 |
| `facts` | list[str] | [] | 事实信息列表 |
| `step_num` | int | 1 | 历史步骤数 |
| `to_user` | bool | False | 是否将输出返回给用户 |
| `enable_filling` | bool | False | 是否需要进行自动参数填充 |

## 错误处理

Slot工具包含以下错误处理机制：

### 1. JSON解析错误

- LLM输出格式不正确时的异常处理
- 使用try-catch捕获JSON解析异常
- 解析失败时返回空字典

### 2. Schema验证错误

- JSON Schema格式错误检测
- 验证器初始化失败处理
- 字段验证失败时的错误提取
