# Empty工具模块文档

## 概述

Empty工具是一个占位符工具，用于在工作流中提供空白节点功能。它不执行任何实际的操作，主要用于工作流设计中的占位、测试或作为流程控制节点。Empty工具是最简单的Call实现，展示了CoreCall框架的基本结构和生命周期。

## 功能特性

- **占位符功能**：提供空白节点，用于工作流占位
- **多语言支持**：支持中文和英文两种语言
- **最小化实现**：展示CoreCall框架的基本结构
- **零副作用**：不执行任何实际操作，确保系统稳定性
- **结构化数据**：基于Pydantic模型进行数据验证和序列化

## 核心组件

### 1. Empty类

Empty工具的核心实现类，继承自`CoreCall`基类，是所有Call实现中最简单的示例。

### 2. 主要属性

| 属性名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `input_model` | type[DataBase] | DataBase | 输入模型类型 |
| `output_model` | type[DataBase] | DataBase | 输出模型类型 |
| `to_user` | bool | False | 是否将输出返回给用户 |
| `enable_filling` | bool | False | 是否需要进行自动参数填充 |

### 3. 核心方法

- `info()`: 返回工具的多语言名称和描述
- `instance()`: 创建工具实例（继承自CoreCall）
- `_init()`: 初始化工具输入
- `_exec()`: 执行工具逻辑（空实现）
- `exec()`: 公共执行接口（继承自CoreCall）

## 数据结构

Empty工具的数据结构非常简单，它使用DataBase作为输入和输出模型：

```mermaid
classDiagram
    class Empty {
        +input_model: type[DataBase]
        +output_model: type[DataBase]
        +to_user: bool
        +enable_filling: bool
        +info() CallInfo
        +_init() DataBase
        +_exec() AsyncGenerator
    }

    class CallInfo {
        +name: str
        +description: str
    }

    class CallOutputChunk {
        +type: CallOutputType
        +content: str | dict
    }

    Empty --> CallInfo : 返回
    Empty --> CallOutputChunk : 生成

    note for Empty "继承自CoreCall基类<br/>使用DataBase作为输入输出模型<br/>详见core.md"
```

### 数据模型说明

- **CallInfo**: 包含工具名称和描述的信息类
- **CallOutputChunk**: Call的输出块，包含类型和内容
- **Empty**: 主要的工具类，使用DataBase作为输入和输出模型(详见[core.md](core.md))

### 数据流转关系

```mermaid
graph LR
    A[CallVars] --> B[Empty工具]
    B --> C[DataBase输入]
    C --> D[空执行逻辑]
    D --> E[CallOutputChunk输出]
    
    subgraph "输入数据"
        A1[call_vars: 系统变量]
    end
    
    subgraph "处理过程"
        B1[初始化DataBase]
        B2[空执行]
    end
    
    subgraph "输出数据"
        E1[type: DATA]
        E2[content]
    end
    
    A1 --> B1
    B1 --> B2
    B2 --> E1
    B2 --> E2
```

## 工作流程

Empty工具的工作流程非常简单，主要展示Call的基本生命周期：

```mermaid
graph TD
    A[开始] --> B[接收CallVars]
    B --> C[初始化DataBase]
    C --> D[执行空逻辑]
    D --> E[生成空输出]
    E --> F[结束]
    
    subgraph "初始化阶段"
        B1[_init方法]
        B2[返回DataBase实例]
    end
    
    subgraph "执行阶段"
        D1[_exec方法]
        D2[生成CallOutputChunk]
        D3[type: DATA]
        D4[content]
    end
    
    B --> B1
    B1 --> B2
    B2 --> D1
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D4 --> E
```

## 执行时序图

```mermaid
sequenceDiagram
    participant E as StepExecutor
    participant EMP as Empty
    participant C as CoreCall
    
    E->>EMP: instance(executor, node)
    EMP->>C: 继承CoreCall.instance()
    C->>EMP: _set_input(executor)
    EMP->>EMP: _init(call_vars)
    EMP-->>C: 返回DataBase()
    C->>EMP: 设置input属性
    
    E->>EMP: exec(executor, input_data)
    EMP->>C: 继承CoreCall.exec()
    C->>EMP: _exec(input_data)
    EMP->>EMP: 创建CallOutputChunk
    EMP-->>C: 返回空输出
    C->>EMP: _after_exec(input_data)
    C-->>E: 返回CallOutputChunk
```

## 核心实现

### 1. 类定义

```python
class Empty(CoreCall, input_model=DataBase, output_model=DataBase):
    """空Call"""
```

Empty类继承自CoreCall，并指定输入和输出模型都为DataBase，这是最简单的配置。

### 2. 多语言信息

```python
@classmethod
def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
    i18n_info = {
        LanguageType.CHINESE: CallInfo(name="空白", description="空白节点，用于占位"),
        LanguageType.ENGLISH: CallInfo(name="Empty", description="Empty node, used for placeholder"),
    }
    return i18n_info[language]
```

提供中英文两种语言的名称和描述信息。

### 3. 初始化方法

```python
async def _init(self, call_vars: CallVars) -> DataBase:
    return DataBase()
```

返回一个空的DataBase实例，不进行任何处理。

### 4. 执行方法

```python
async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
    output = CallOutputChunk(type=CallOutputType.DATA, content={})
    yield output
```

生成一个空的DATA类型输出块，内容为空字典。

## 使用示例

### 基本使用

```python
# 创建Empty工具实例
empty_tool = await Empty.instance(executor, node)

# 执行空操作
async for chunk in empty_tool.exec(executor, input_data):
    if chunk.type == CallOutputType.DATA:
        print(f"输出内容: {chunk.content}")  # 输出: {}
```

### 在工作流中使用

```python
# 工作流配置示例
workflow_config = {
    "nodes": [
        {
            "id": "start",
            "type": "start",
            "name": "开始"
        },
        {
            "id": "placeholder",
            "type": "Empty",
            "name": "占位节点",
            "description": "用于占位的空白节点"
        },
        {
            "id": "end",
            "type": "end", 
            "name": "结束"
        }
    ],
    "edges": [
        {"from": "start", "to": "placeholder"},
        {"from": "placeholder", "to": "end"}
    ]
}
```

## 配置参数

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `input_model` | type[DataBase] | DataBase | 输入模型类型 |
| `output_model` | type[DataBase] | DataBase | 输出模型类型 |
| `to_user` | bool | False | 是否将输出返回给用户 |
| `enable_filling` | bool | False | 是否需要进行自动参数填充 |

## 应用场景

### 1. 工作流占位

```mermaid
graph LR
    A[开始] --> B[数据处理]
    B --> C[空白占位]
    C --> D[结果输出]
    
    style C fill:#f9f9f9,stroke:#333,stroke-width:2px
```

在工作流设计中使用Empty节点作为占位符，为未来的功能扩展预留位置。

### 2. 流程测试

在开发阶段使用Empty节点测试工作流的连接性和流程逻辑，而不执行实际的功能。

## 依赖关系

- `CoreCall`: 基础调用框架，提供通用的Call生命周期管理(详见[core.md](core.md))
- `DataBase`: 基础数据模型，提供通用的数据验证和序列化功能(详见[core.md](core.md))
- `CallInfo`: 工具信息模型，包含名称和描述
- `CallOutputChunk`: 输出块模型，定义输出格式
- `CallVars`: 系统变量模型，包含执行上下文信息(详见[core.md](core.md))

## 相关模块

- `apps/scheduler/call/core.py`: CoreCall基类实现
- `apps/scheduler/call/empty.py`: Empty工具实现
- `apps/schemas/scheduler.py`: 调度器相关Schema定义
- `apps/schemas/enum_var.py`: 枚举类型定义
