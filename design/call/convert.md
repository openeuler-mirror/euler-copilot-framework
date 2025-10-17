# Convert模块文档

## 1. 模块概述

Convert模块是欧拉助手框架中的一个核心工具，主要用于对生成的文字信息和原始数据进行格式化处理。该模块基于Jinja2模板引擎，支持灵活的模板语法，可以将各种数据转换为特定格式的文本或结构化数据，为系统中的数据展示和传递提供了强大的支持。

**主要功能特性：**

- 支持Jinja2模板语法的文本格式化
- 支持JSON数据的模板渲染和解析
- 提供多语言的工具名称和描述信息
- 采用异步编程模式，支持流式输出
- 集成了丰富的上下文变量，如时间、历史记录、问题等

## 2. 代码结构

Convert模块位于 `apps/scheduler/call/convert/` 目录下，包含以下三个主要文件：

```text
apps/scheduler/call/convert/
├── __init__.py    # 模块初始化文件
├── convert.py     # 核心实现代码
└── schema.py      # 输入输出数据结构定义
```

## 3. 核心类与方法

### 3.1 Convert类

`Convert` 类是模块的核心，继承自 `CoreCall` 基类，实现了模板转换的核心逻辑。

### 3.2 主要属性

| 属性名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| `text_template` | str \| None | None | 自然语言信息的格式化模板，使用Jinja2语法 |
| `data_template` | str \| None | None | 原始数据的格式化模板，使用Jinja2语法 |

### 3.3 主要方法

#### 3.3.1 info方法

**功能描述**：提供Convert工具的名称和描述信息，支持多语言国际化。

**主要特点**：

- 支持中英文两种语言切换
- 返回标准的CallInfo对象，包含工具名称和功能描述
- 中文版本名称为"模板转换"，英文版本名称为"Convert"
- 描述信息说明了工具的核心功能：使用Jinja2语法格式化自然语言信息和原始数据

**实现逻辑**：

1. 接收语言类型参数，默认为中文
2. 根据语言类型返回对应的工具信息
3. 中文环境下返回"模板转换"名称和中文描述
4. 英文环境下返回"Convert"名称和英文描述

#### 3.3.2 _init方法

**功能描述**：初始化Convert工具，准备模板渲染所需的环境和变量。

**主要特点**：

- 继承自CoreCall基类并进行扩展
- 创建SandboxedEnvironment环境以安全地执行模板
- 收集和准备模板渲染所需的额外变量（如时间、历史记录、问题等）

**实现逻辑**：

1. 调用父类的初始化方法，完成基础设置
2. 从调用变量中提取历史数据和问题信息
3. 创建安全的Jinja2沙盒环境，配置模板处理选项
4. 获取当前时间（使用亚洲/上海时区）
5. 构建扩展变量字典，包含：
   - 当前时间
   - 历史记录数据
   - 用户问题
   - 系统背景信息
   - 相关ID信息
6. 返回ConvertInput对象，包含模板内容和扩展变量

#### 3.3.3 _exec方法

**功能描述**：执行模板转换操作，处理文本模板和数据模板，并流式返回结果。

**主要特点**：

- 分别处理文本模板和数据模板
- 对模板渲染过程中的异常进行捕获和处理
- 支持流式输出，分别返回文本和数据两种类型的结果

**实现逻辑**：

**文本模板处理：**

1. 检查是否提供了文本模板
2. 如果存在模板，使用Jinja2环境进行渲染
3. 将扩展变量传递给模板进行渲染
4. 捕获渲染异常并抛出详细的错误信息
5. 如果未提供模板，返回默认提示信息

**数据模板处理：**

1. 检查是否提供了数据模板
2. 如果存在模板，先进行Jinja2渲染得到字符串结果
3. 尝试将渲染结果解析为JSON对象
4. 捕获渲染或解析异常并抛出详细错误信息
5. 如果未提供模板，返回包含默认消息的对象

**结果输出：**

1. 以流式方式返回文本类型的结果块
2. 以流式方式返回数据类型的结果块
3. 每个结果块包含对应的内容和类型标识

## 4. 数据结构

### 4.1 核心数据结构关系

```mermaid
classDiagram
    class Convert {
        +text_template: str | None
        +data_template: str | None
        +info()
        +_init()
        +_exec()
    }

    class ConvertInput {
        +text_template: str | None
        +data_template: str | None
        +extras: dict[str, Any]
    }

    class ConvertOutput {
        +text: str
        +data: dict
    }

    class SandboxedEnvironment {
        +from_string()
    }

    Convert --> ConvertInput
    Convert --> ConvertOutput
    Convert --> SandboxedEnvironment

    note for Convert "继承自CoreCall基类<br/>详见core.md"
```

### 4.2 详细字段说明

#### 4.2.1 ConvertInput 输入数据结构

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `text_template` | `str \| None` | 否 | 自然语言信息的格式化模板，Jinja2语法 | `"当前时间：{{ time }}"` |
| `data_template` | `str \| None` | 否 | 原始数据的格式化模板，Jinja2语法 | `"{\"question\": \"{{ question }}\", \"time\": \"{{ time }}\"}"` |
| `extras` | `dict[str, Any]` | 是 | 模板渲染的额外变量 | `{"time": "2023-01-01 12:00:00", "question": "你好"}` |

#### 4.2.2 ConvertOutput 输出数据结构

| 字段名 | 类型 | 必需 | 说明 | 示例值 |
|--------|------|------|------|--------|
| `text` | `str` | 是 | 格式化后的文字信息 | `"当前时间：2023-01-01 12:00:00"` |
| `data` | `dict` | 是 | 格式化后的结果数据 | `{"question": "你好", "time": "2023-01-01 12:00:00"}` |

#### 4.2.3 extras 扩展变量结构

`extras` 字段包含模板渲染所需的所有变量，来源于 CallVars 系统变量(详见[core.md](core.md#callvars-系统变量结构))。主要包括：

| 字段名 | 说明 |
|--------|------|
| `time` | 当前时间（亚洲/上海时区） |
| `history` | 历史步骤数据字典 |
| `question` | 用户问题 |
| `background` | 背景信息 |
| `ids` | ID信息集合 |

## 5. 流程图与时序图

### 5.1 模块工作流程图

```mermaid
flowchart TD
    A[开始] --> B[初始化Convert工具]
    B --> C{是否提供文本模板?}
    C -- 是 --> D[渲染文本模板]
    C -- 否 --> E[设置默认文本]
    D --> F{是否提供数据模板?}
    E --> F
    F -- 是 --> G[渲染数据模板]
    F -- 否 --> H[设置默认数据]
    G --> I[流式输出结果]
    H --> I
    I --> J[结束]
    
    subgraph 异常处理
        D -- 渲染错误 --> K[抛出文本模板错误]
        G -- 渲染错误 --> L[抛出数据模板错误]
        K --> M[返回错误信息]
        L --> M
        M --> J
    end
```

### 5.2 模块调用时序图

```mermaid
sequenceDiagram
    participant Executor as 执行器
    participant Convert as Convert模块
    participant Jinja2 as Jinja2模板引擎
    
    Executor ->> Convert: 初始化工具(_init)
    Convert -->> Executor: 返回ConvertInput
    Executor ->> Convert: 执行工具(_exec)
    
    par 文本模板处理
        Convert ->> Jinja2: 创建文本模板(from_string)
        Jinja2 -->> Convert: 返回模板对象
        Convert ->> Jinja2: 渲染模板(render)
        Jinja2 -->> Convert: 返回渲染结果
    and 数据模板处理
        Convert ->> Jinja2: 创建数据模板(from_string)
        Jinja2 -->> Convert: 返回模板对象
        Convert ->> Jinja2: 渲染模板(render)
        Jinja2 -->> Convert: 返回渲染结果
        Convert ->> Convert: 解析JSON数据(json.loads)
    end
    
    Convert -->> Executor: 流式返回文本结果(CallOutputChunk)
    Convert -->> Executor: 流式返回数据结果(CallOutputChunk)
```

## 6. 输入输出示例

### 6.1 文本模板示例

**配置参数：**

```json
{
  "text_template": "用户的问题是：{{ question }}\n当前时间：{{ time }}\n历史步骤数：{{ history | length }}"
}
```

**输入数据（CallVars）：**

```json
{
  "question": "什么是欧拉助手?",
  "time": "2023-01-01 12:00:00",
  "history": {"step1": {"result": "数据1"}, "step2": {"result": "数据2"}}
}
```

**输出结果（文本部分）：**

```text
用户的问题是：什么是欧拉助手?
当前时间：2023-01-01 12:00:00
历史步骤数：2
```

### 6.2 数据模板示例

**配置参数：**

```json
{
  "data_template": "{\"question\": \"{{ question }}\", \"timestamp\": \"{{ time }}\", \"history_count\": {{ history | length }} }"
}
```

**输入数据（CallVars）：**

```json
{
  "question": "什么是欧拉助手?",
  "time": "2023-01-01 12:00:00",
  "history": {"step1": {"result": "数据1"}, "step2": {"result": "数据2"}}
}
```

**输出结果（数据部分）：**

```json
{
  "question": "什么是欧拉助手?",
  "timestamp": "2023-01-01 12:00:00",
  "history_count": 2
}
```

## 7. 错误处理

Convert模块包含完善的错误处理机制，主要针对以下两种错误情况：

1. **文本模板渲染错误**：当文本模板语法错误或渲染过程中出现异常时，会抛出包含详细错误信息的CallError异常。
2. **数据模板渲染错误**：当数据模板语法错误、渲染过程中出现异常或渲染结果无法解析为JSON时，会抛出包含详细错误信息的CallError异常。

错误信息包含错误描述和相关上下文数据，有助于快速定位和解决问题。

## 8. 代码优化建议

1. **模板缓存机制**：对于频繁使用的模板，可以考虑添加缓存机制，避免重复解析模板字符串，提高性能。

2. **模板语法检查**：在初始化阶段，可以先对模板语法进行预检查，提前发现并报告语法错误，提高用户体验。

3. **数据类型安全**：在解析JSON数据时，可以添加更严格的数据类型验证，确保输出数据符合预期的格式和类型。

4. **自定义过滤器扩展**：可以考虑扩展Jinja2环境，添加自定义过滤器，提供更多数据处理和格式化能力。

5. **国际化支持增强**：当前的默认提示信息仅支持中文，可以考虑将其纳入多语言支持体系，根据系统语言自动切换。
