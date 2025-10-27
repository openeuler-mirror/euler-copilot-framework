# Step Executor 模块设计文档

## 1. 概述

Step Executor 是工作流执行器中负责单个步骤执行的核心模块，它将工作流中定义的每个步骤转换为实际的 Call 调用，并管理步骤的完整生命周期。

核心特性：

- **Call 实例化**：动态加载和实例化各种 Call 类
- **参数管理**：支持参数覆盖和动态参数填充
- **自动填参**：集成 Slot 填充机制，自动补充缺失参数
- **流式输出**：支持流式处理 Call 的输出内容
- **错误处理**：完善的异常捕获和错误状态管理
- **上下文管理**：维护步骤执行历史用于后续步骤

## 2. 架构设计

### 2.1 类结构

```mermaid
classDiagram
    class BaseExecutor {
        <<abstract>>
        +TaskData task
        +MessageQueue msg_queue
        +LLMConfig llm
        +str question
        +init()* None
        +run()* None
        -_load_history(n: int) None
        -_push_message(event_type, data) None
    }

    class StepExecutor {
        +StepQueueItem step
        +ExecutorBackground background
        +NodeInfo node
        -str _call_id
        -CoreCall obj
        +check_cls(call_cls)$ bool
        +get_call_cls(call_id)$ CoreCall
        +init() None
        +run() None
        -_run_slot_filling() None
        -_process_chunk(iterator, to_user) str|dict
    }

    class CoreCall {
        <<abstract>>
        +str name
        +str description
        +NodeInfo node
        +bool enable_filling
        +bool to_user
        +type~DataBase~ input_model
        +type~DataBase~ output_model
        +dict input
        +info(language)$ CallInfo
        +instance(executor, node, kwargs)$ Self
        -_init(call_vars)* DataBase
        -_exec(input_data)* AsyncGenerator
        -_after_exec(input_data) None
        +exec(executor, input_data) AsyncGenerator
    }

    class StepQueueItem {
        +UUID step_id
        +Step step
        +bool enable_filling
        +bool to_user
    }

    class Step {
        +str name
        +str description
        +str type
        +str node
        +dict params
    }

    class NodeInfo {
        +str id
        +str callId
        +str name
        +dict knownParams
        +dict overrideInput
        +dict overrideOutput
    }

    class ExecutorHistory {
        +UUID taskId
        +UUID executorId
        +str executorName
        +ExecutorStatus executorStatus
        +UUID stepId
        +str stepName
        +str stepType
        +StepStatus stepStatus
        +dict inputData
        +dict outputData
        +dict extraData
    }

    BaseExecutor <|-- StepExecutor
    StepExecutor --> StepQueueItem : uses
    StepExecutor --> CoreCall : instantiates
    StepExecutor --> NodeInfo : loads
    StepExecutor --> ExecutorHistory : creates
    StepQueueItem --> Step : contains
    CoreCall --> NodeInfo : references
```

### 2.2 核心组件关系

```mermaid
graph TB
    A[StepExecutor] --> B[StepQueueItem]
    A --> C[NodeManager]
    A --> D[Call Pool]
    A --> E[CoreCall Instance]
    A --> F[Slot Filling]

    B --> G[Step Definition]
    C --> H[NodeInfo]
    D --> I[Call Classes]
    E --> J[Input Data]
    E --> K[Output Data]
    F --> L[SlotOutput]

    A --> M[TaskData]
    M --> N[ExecutorCheckpoint]
    M --> O[ExecutorHistory List]
    M --> P[TaskRuntime]

    A --> Q[MessageQueue]
    Q --> R[Event Bus]

    style A fill:#f9f,stroke:#333,stroke-width:4px
    style E fill:#bbf,stroke:#333,stroke-width:2px
    style F fill:#bfb,stroke:#333,stroke-width:2px
    style M fill:#fbb,stroke:#333,stroke-width:2px
```

### 2.3 Call 类型系统

```mermaid
graph TB
    A[CoreCall] --> B[Empty]
    A --> C[Summary]
    A --> D[FactsCall]
    A --> E[Slot]
    A --> F[Custom Calls]

    F --> G[LLM Call]
    F --> H[API Call]
    F --> I[SQL Call]
    F --> J[Choice Call]

    B -.->|特殊节点| K[SpecialCallType]
    C -.->|特殊节点| K
    D -.->|特殊节点| K
    E -.->|特殊节点| K

    G -.->|Pool加载| L[Call Pool]
    H -.->|Pool加载| L
    I -.->|Pool加载| L
    J -.->|Pool加载| L

    style A fill:#f9f,stroke:#333,stroke-width:4px
    style K fill:#bbf,stroke:#333,stroke-width:2px
    style L fill:#bfb,stroke:#333,stroke-width:2px
```

## 3. 执行流程

### 3.1 主流程图

```mermaid
flowchart TD
    Start([步骤开始]) --> Init[init: 初始化步骤]

    Init --> LoadState[加载任务状态]
    LoadState --> SetState[设置步骤ID和状态]

    SetState --> GetNode{获取Node信息}
    GetNode -->|成功| LoadNode[加载NodeInfo]
    GetNode -->|失败/特殊| LoadSpecial[加载特殊Call]

    LoadNode --> GetCallCls[get_call_cls: 获取Call类]
    LoadSpecial --> GetCallCls

    GetCallCls --> CheckCls[check_cls: 验证Call标准]
    CheckCls -->|失败| Error1[抛出异常]
    CheckCls -->|成功| MergeParams[合并参数]

    MergeParams --> Instance[Call.instance: 实例化]
    Instance -->|失败| Error2[记录异常并抛出]
    Instance -->|成功| Run[run: 运行步骤]

    Run --> CheckFilling{是否启用填参?}
    CheckFilling -->|是| SlotFilling[_run_slot_filling]
    CheckFilling -->|否| UpdateStatus1[更新状态为RUNNING]

    SlotFilling --> InitSlot[初始化Slot对象]
    InitSlot --> PushSlotInput[推送填参输入]
    PushSlotInput --> ExecSlot[执行Slot填充]
    ExecSlot --> CheckRemaining{是否有缺失参数?}

    CheckRemaining -->|是| SetParam[设置状态为PARAM]
    CheckRemaining -->|否| SetSuccess1[设置状态为SUCCESS]

    SetParam --> PushSlotOutput[推送填参输出]
    SetSuccess1 --> PushSlotOutput
    PushSlotOutput --> UpdateInput[更新obj.input]
    UpdateInput --> UpdateStatus1

    UpdateStatus1 --> PushInput[推送STEP_INPUT]
    PushInput --> ExecCall[obj.exec: 执行Call]

    ExecCall --> ProcessChunk[_process_chunk: 处理输出]
    ProcessChunk -->|异常| HandleError[异常处理]
    ProcessChunk -->|成功| UpdateStatus2[更新状态为SUCCESS]

    HandleError --> CheckErrorType{错误类型?}
    CheckErrorType -->|CallError| SetCallError[设置CallError消息]
    CheckErrorType -->|其他| SetGenericError[设置通用错误]

    SetCallError --> SetErrorStatus[状态设为ERROR]
    SetGenericError --> SetErrorStatus
    SetErrorStatus --> PushEmptyOutput[推送空输出]
    PushEmptyOutput --> End1([结束])

    UpdateStatus2 --> CalcTime[计算执行时间]
    CalcTime --> BuildHistory[构建ExecutorHistory]
    BuildHistory --> AddContext[添加到上下文]
    AddContext --> PushOutput[推送STEP_OUTPUT]
    PushOutput --> End2([成功结束])

    Error1 --> End3([异常结束])
    Error2 --> End3

    style Init fill:#e1f5ff
    style Run fill:#e1f5ff
    style SlotFilling fill:#fff4e1
    style ProcessChunk fill:#e7f5e1
    style HandleError fill:#ffe1e1
```

### 3.2 Call 实例化流程

```mermaid
sequenceDiagram
    participant SE as StepExecutor
    participant NM as NodeManager
    participant Pool as Call Pool
    participant CC as CoreCall Class
    participant Obj as Call Instance

    SE->>SE: init()

    alt 有Node ID
        SE->>NM: get_node(node_id)
        alt Node存在
            NM-->>SE: NodeInfo
            SE->>SE: 保存NodeInfo
            SE->>SE: get_call_cls(node.callId)
        else Node不存在
            NM-->>SE: ValueError
            SE->>SE: node = None
            SE->>SE: get_call_cls(node_id)
        end
    end

    alt 特殊Call类型
        SE->>SE: 返回内置类
        Note right of SE: Empty, Summary,<br/>FactsCall, Slot
    else 普通Call
        SE->>Pool: get_call(call_id)
        Pool-->>SE: Call Class
        SE->>SE: check_cls(call_cls)
        alt 验证失败
            SE-->>SE: 抛出ValueError
        end
    end

    SE->>SE: 合并参数
    Note right of SE: node.knownParams<br/>+ step.params

    SE->>CC: instance(executor, node, **params)
    CC->>Obj: 创建实例
    CC->>Obj: _set_input(executor)
    Obj->>Obj: _assemble_call_vars()
    Obj->>Obj: _init(call_vars)
    Obj-->>CC: input_data (DataBase)
    CC->>Obj: 设置input属性
    CC-->>SE: Call实例

    SE->>SE: self.obj = instance
```

### 3.3 自动填参流程

```mermaid
flowchart TD
    Start([开始填参]) --> CheckEnable{obj.enable_filling?}
    CheckEnable -->|否| Skip([跳过填参])
    CheckEnable -->|是| SaveState[暂存当前State]

    SaveState --> UpdateState1[更新stepId为随机UUID]
    UpdateState1 --> UpdateState2[更新stepName为'自动参数填充']
    UpdateState2 --> UpdateState3[更新stepStatus为RUNNING]

    UpdateState3 --> GetSchema[获取input_model的JSON Schema]
    GetSchema --> ApplyOverride[应用node.overrideInput]
    ApplyOverride --> InitSlot[初始化Slot实例]

    InitSlot --> PushInput[推送STEP_INPUT事件]
    PushInput --> ExecSlot[执行slot_obj.exec]

    ExecSlot --> IterChunks[遍历输出chunk]
    IterChunks --> ParseResult[解析为SlotOutput]

    ParseResult --> CheckRemaining{remaining_schema存在?}
    CheckRemaining -->|是| SetParam[stepStatus = PARAM]
    CheckRemaining -->|否| SetSuccess[stepStatus = SUCCESS]

    SetParam --> PushOutput[推送STEP_OUTPUT]
    SetSuccess --> PushOutput

    PushOutput --> UpdateObjInput[更新obj.input]
    UpdateObjInput --> RestoreState[恢复原State]
    RestoreState --> End([填参完成])

    style InitSlot fill:#fff4e1
    style ExecSlot fill:#e7f5e1
    style CheckRemaining fill:#ffe1f5
```

### 3.4 Chunk 处理流程

```mermaid
flowchart TD
    Start([开始处理]) --> InitContent[初始化content = '']
    InitContent --> IterChunks[遍历AsyncGenerator]

    IterChunks --> GetChunk{获取chunk}
    GetChunk -->|有数据| CheckType{chunk类型?}
    GetChunk -->|结束| Return([返回content])

    CheckType -->|非CallOutputChunk| Error[抛出TypeError]
    CheckType -->|正确| CheckContentType{content类型?}

    CheckContentType -->|str| HandleStr[处理字符串]
    CheckContentType -->|dict| HandleDict[处理字典]

    HandleStr --> CheckContentInit1{当前content是str?}
    CheckContentInit1 -->|否| ResetStr[重置为空字符串]
    CheckContentInit1 -->|是| AppendStr[追加字符串]
    ResetStr --> AppendStr

    HandleDict --> CheckContentInit2{当前content是dict?}
    CheckContentInit2 -->|否| ResetDict[重置为空字典]
    CheckContentInit2 -->|是| UpdateDict[更新字典]
    ResetDict --> UpdateDict

    AppendStr --> CheckToUser{to_user参数?}
    UpdateDict --> CheckToUser

    CheckToUser -->|true且为str| PushText[推送TEXT_ADD事件]
    CheckToUser -->|true且为dict| PushStepType[推送step.type事件]
    CheckToUser -->|false| Skip[跳过]

    PushText --> UpdateFullAnswer[更新fullAnswer]
    UpdateFullAnswer --> IterChunks
    PushStepType --> IterChunks
    Skip --> IterChunks

    Error --> End([异常结束])

    style HandleStr fill:#e1f5ff
    style HandleDict fill:#fff4e1
    style PushText fill:#e7f5e1
```

## 4. 时序图

### 4.1 完整步骤执行时序

```mermaid
sequenceDiagram
    actor User
    participant Scheduler
    participant SE as StepExecutor
    participant NM as NodeManager
    participant Pool as Call Pool
    participant Call as CoreCall
    participant Slot as Slot Call
    participant Queue as MessageQueue

    Scheduler->>SE: 创建StepExecutor
    activate SE

    Scheduler->>SE: init()
    SE->>SE: 设置stepId/stepType/stepName
    SE->>NM: get_node(node_id)
    NM-->>SE: NodeInfo | None

    alt Node存在
        SE->>Pool: get_call(node.callId)
        Pool-->>SE: Call Class
    else 特殊节点
        SE->>SE: 获取内置Call类
    end

    SE->>SE: check_cls(call_cls)
    SE->>SE: 合并参数
    SE->>Call: instance(executor, node, **params)
    Call->>Call: _set_input(executor)
    Call->>Call: _init(call_vars)
    Call-->>SE: Call实例

    Scheduler->>SE: run()
    SE->>SE: _run_slot_filling()

    alt enable_filling = true
        SE->>SE: 暂存State
        SE->>Slot: instance(executor, node, schema)
        Slot-->>SE: Slot实例
        SE->>Queue: STEP_INPUT (Slot)
        Queue-->>User: 填参输入事件

        SE->>Slot: exec(executor, input)
        loop 遍历chunk
            Slot-->>SE: CallOutputChunk
        end

        alt 有缺失参数
            SE->>SE: stepStatus = PARAM
        else 参数完整
            SE->>SE: stepStatus = SUCCESS
        end

        SE->>Queue: STEP_OUTPUT (SlotOutput)
        Queue-->>User: 填参结果
        SE->>SE: 更新obj.input
        SE->>SE: 恢复State
    end

    SE->>SE: stepStatus = RUNNING
    SE->>Queue: STEP_INPUT
    Queue-->>User: 步骤输入

    SE->>Call: exec(executor, obj.input)

    loop 流式输出
        Call-->>SE: CallOutputChunk
        SE->>SE: 累积content

        alt to_user = true
            alt content是str
                SE->>Queue: TEXT_ADD
                Queue-->>User: 流式文本
                SE->>SE: 更新fullAnswer
            else content是dict
                SE->>Queue: step.type事件
                Queue-->>User: 结构化数据
            end
        end
    end

    alt 执行成功
        SE->>SE: stepStatus = SUCCESS
        SE->>SE: 计算执行时间
        SE->>SE: 构建ExecutorHistory
        SE->>SE: 添加到context
        SE->>Queue: STEP_OUTPUT
        Queue-->>User: 步骤输出
    else 执行失败
        SE->>SE: stepStatus = ERROR
        alt CallError
            SE->>SE: 设置详细错误信息
        else 其他异常
            SE->>SE: 设置通用错误
        end
        SE->>Queue: STEP_OUTPUT (空)
        Queue-->>User: 错误通知
    end

    deactivate SE
```

### 4.2 Call 验证时序

```mermaid
sequenceDiagram
    participant SE as StepExecutor
    participant Pool as Call Pool
    participant CC as Call Class
    participant Inspect as inspect module

    SE->>SE: get_call_cls(call_id)

    alt 特殊Call类型
        SE->>SE: 匹配SpecialCallType
        alt EMPTY
            SE-->>SE: Empty类
        else SUMMARY
            SE-->>SE: Summary类
        else FACTS
            SE-->>SE: FactsCall类
        else SLOT
            SE-->>SE: Slot类
        end
    else 普通Call
        SE->>Pool: get_call(call_id)
        Pool-->>SE: call_cls

        SE->>SE: check_cls(call_cls)

        SE->>CC: hasattr(_init)?
        CC-->>SE: bool

        alt 无_init
            SE-->>SE: flag = False
        else 有_init
            SE->>CC: callable(_init)?
            CC-->>SE: bool
            alt 不可调用
                SE-->>SE: flag = False
            end
        end

        SE->>CC: hasattr(_exec)?
        CC-->>SE: bool

        alt 无_exec
            SE-->>SE: flag = False
        else 有_exec
            SE->>Inspect: isasyncgenfunction(_exec)
            Inspect-->>SE: bool
            alt 不是异步生成器
                SE-->>SE: flag = False
            end
        end

        SE->>CC: hasattr(info)?
        CC-->>SE: bool

        alt 无info
            SE-->>SE: flag = False
        else 有info
            SE->>CC: callable(info)?
            CC-->>SE: bool
            alt 不可调用
                SE-->>SE: flag = False
            end
        end

        alt flag = False
            SE-->>SE: 抛出ValueError
        end
    end

    SE-->>SE: 返回call_cls
```

### 4.3 错误处理时序

```mermaid
sequenceDiagram
    participant SE as StepExecutor
    participant Call as CoreCall
    participant Queue as MessageQueue
    actor User

    SE->>Call: exec(executor, input)

    alt 执行过程中异常
        Call-->>SE: 抛出异常

        alt CallError类型
            SE->>SE: 提取message和data
            SE->>SE: stepStatus = ERROR
            SE->>SE: errorMessage = {err_msg, data}
        else 其他异常
            SE->>SE: 记录异常堆栈
            SE->>SE: stepStatus = ERROR
            SE->>SE: errorMessage = {data: {}}
        end

        SE->>Queue: STEP_OUTPUT (空字典)
        Queue-->>User: 错误通知

        SE->>SE: return (终止run方法)
    else 正常输出但失败标识
        loop 遍历chunk
            Call-->>SE: CallOutputChunk(error内容)
            SE->>SE: 累积错误信息
        end

        SE->>SE: stepStatus = SUCCESS
        Note right of SE: 由上层判断输出<br/>是否表示失败

        SE->>SE: 构建History
        SE->>Queue: STEP_OUTPUT (错误内容)
        Queue-->>User: 输出结果
    end
```

## 5. 核心方法详解

### 5.1 初始化方法

#### init() - 初始化步骤执行器

**功能说明**：在步骤执行前初始化所有必要的组件，包括加载 Node、获取 Call 类、实例化 Call 对象。

**执行步骤**：

1. 检查任务状态（task.state）是否存在，不存在则抛出异常
2. 将步骤信息写入任务状态：
   - `stepId`: 当前步骤的唯一标识
   - `stepType`: 步骤类型（转换为字符串）
   - `stepName`: 步骤名称
3. 尝试从 NodeManager 获取 Node 详情：
   - 成功则保存到 `self.node`
   - 失败则设置为 `None`（可能是内置特殊节点）
4. 根据 Node 信息获取 Call 类：
   - 有 Node：使用 `node.callId` 获取
   - 无 Node：直接使用 `node_id`（特殊节点）
5. 合并参数：
   - 基础参数：`node.knownParams`（如果存在）
   - 覆盖参数：`step.params`（用户指定参数优先）
6. 实例化 Call 类并保存到 `self.obj`

**异常处理**：

- **RuntimeError**: 任务状态不存在
- **ValueError**: Node ID 不存在或 Call 类验证失败
- **其他异常**: 记录日志并重新抛出

**使用示例**：

```python
step_executor = StepExecutor(
    task=task_data,
    msg_queue=message_queue,
    llm=llm_config,
    question=user_question,
    step=step_queue_item,
    background=executor_background
)
await step_executor.init()
# 此时 step_executor.obj 已经是实例化的 Call 对象
```

---

#### check_cls(call_cls) - 检查 Call 类是否符合标准

**功能说明**：静态方法，验证 Call 类是否实现了必需的方法和接口。

**验证项**：

| 属性/方法 | 类型要求 | 说明 |
|----------|---------|------|
| `_init` | 可调用 | 初始化方法，返回输入数据 |
| `_exec` | 异步生成器函数 | 执行方法，流式输出结果 |
| `info` | 可调用 | 返回 Call 的元信息 |

**返回值**：

- `True`: 所有验证通过
- `False`: 至少有一项验证失败

**使用场景**：在从 Pool 加载 Call 类后，实例化前进行验证。

---

#### get_call_cls(call_id) - 获取并验证 Call 类

**功能说明**：静态方法，根据 Call ID 获取对应的 Call 类，支持特殊节点和池加载。

**特殊节点映射**：

```python
EMPTY -> Empty          # 空节点
SUMMARY -> Summary      # 总结节点
FACTS -> FactsCall      # 事实提取节点
SLOT -> Slot           # 参数填充节点
```

**执行逻辑**：

1. 检查 `call_id` 是否为特殊类型，如果是则直接返回内置类
2. 否则从 Call Pool 获取对应的 Call 类
3. 调用 `check_cls` 验证 Call 类的合法性
4. 验证失败则抛出 `ValueError`

**异常**：

- **ValueError**: Call 不符合标准要求

---

### 5.2 步骤执行方法

#### run() - 运行单个步骤

**功能说明**：步骤执行的主入口方法，协调填参、执行、输出处理和历史记录。

**执行流程**：

```text
检查状态 → 自动填参 → 更新为RUNNING → 推送输入
→ 执行Call → 处理输出 → 更新为SUCCESS → 构建历史 → 推送输出
```

**关键时间节点**：

- `task.runtime.time`: 步骤开始时间（UTC时间戳）
- `task.runtime.fullTime`: 步骤执行总时长（秒）

**输出处理**：

- **字符串输出**: 封装为 `TextAddContent`
- **字典输出**: 直接使用

**历史记录字段**：

```python
ExecutorHistory(
    taskId=任务ID,
    executorId=执行器ID,
    executorName=执行器名称,
    executorStatus=执行器状态,
    stepId=步骤ID,
    stepName=步骤名称,
    stepType=步骤类型,
    stepStatus=步骤状态,
    inputData=输入数据,
    outputData=输出数据
)
```

**异常处理**：

执行失败时：

1. 设置步骤状态为 `ERROR`
2. 推送空的 `STEP_OUTPUT` 事件
3. 设置错误消息到 `task.state.errorMessage`
4. 直接返回（不抛出异常）

---

#### _run_slot_filling() - 运行自动参数填充

**功能说明**：在步骤执行前，如果启用了自动填参，使用 Slot 机制补充缺失的参数。

**前置条件**：

- `self.obj.enable_filling = True`
- 任务状态存在

**执行步骤**：

1. **状态保护**：
   - 暂存当前的 `stepId` 和 `stepName`
   - 生成新的临时步骤ID
   - 设置步骤名称为 "自动参数填充"

2. **初始化 Slot**：

   ```python
   slot_obj = await Slot.instance(
       executor=self,
       node=self.node,
       data=self.obj.input,
       current_schema=self.obj.input_model.model_json_schema(
           override=self.node.overrideInput
       )
   )
   ```

3. **执行填参**：
   - 推送 `STEP_INPUT` 事件
   - 调用 `slot_obj.exec()` 执行填充
   - 解析为 `SlotOutput`

4. **状态判断**：
   - 有 `remaining_schema`: 设置为 `PARAM`（需要用户补充）
   - 无 `remaining_schema`: 设置为 `SUCCESS`（已完全填充）

5. **更新输入**：

   ```python
   self.obj.input.update(result.slot_data)
   ```

6. **恢复状态**：
   - 恢复原 `stepId` 和 `stepName`

**特点**：

- 不存入数据库（相当于虚拟步骤）
- 状态临时变更，不影响主步骤
- 填参结果直接更新到 Call 对象的输入

---

#### _process_chunk(iterator, to_user) - 处理 Chunk 流

**功能说明**：处理 Call 执行过程中的流式输出，支持字符串和字典两种格式。

**参数说明**：

- `iterator`: `AsyncGenerator[CallOutputChunk, None]` - 异步生成器
- `to_user`: `bool` - 是否推送到用户（默认 `False`）

**处理逻辑**：

```python
content: str | dict[str, Any] = ""

async for chunk in iterator:
    # 类型检查
    if not isinstance(chunk, CallOutputChunk):
        raise TypeError("返回结果类型错误")

    # 字符串累积
    if isinstance(chunk.content, str):
        if not isinstance(content, str):
            content = ""  # 类型切换，重置
        content += chunk.content

        if to_user:
            await self._push_message(EventType.TEXT_ADD.value, chunk.content)
            self.task.runtime.fullAnswer += chunk.content

    # 字典更新
    else:
        if not isinstance(content, dict):
            content = {}  # 类型切换，重置
        content = chunk.content

        if to_user:
            await self._push_message(self.step.step.type, chunk.content)

return content
```

**类型切换策略**：

- 当 `content` 类型与 `chunk.content` 类型不匹配时，重置 `content`
- 字符串模式：累加追加
- 字典模式：完全替换

**事件推送**：

- **字符串**: 推送 `TEXT_ADD` 事件，累积到 `fullAnswer`
- **字典**: 推送步骤类型事件（如 `STEP_RUNNING`）

**返回值**：

- 累积的字符串或最终的字典

---

### 5.3 辅助方法

#### _push_message(event_type, data) - 推送消息

继承自 `BaseExecutor`，统一的消息推送接口。

**常用事件类型**：

| 事件类型 | 触发时机 | 数据格式 |
|---------|---------|---------|
| `STEP_INPUT` | 步骤开始执行前 | `obj.input` (dict) |
| `STEP_OUTPUT` | 步骤执行完成后 | 输出数据 (dict) |
| `TEXT_ADD` | 流式文本输出 | `TextAddContent` |
| `EventType(step.type)` | 结构化数据输出 | 自定义格式 |

---

## 6. 数据模型

### 6.1 核心数据结构

```mermaid
erDiagram
    StepExecutor ||--|| StepQueueItem : "has"
    StepExecutor ||--o| NodeInfo : "loads"
    StepExecutor ||--|| CoreCall : "instantiates"
    StepExecutor ||--|| TaskData : "operates"

    StepQueueItem ||--|| Step : "contains"

    TaskData ||--|| Task : "metadata"
    TaskData ||--|| TaskRuntime : "runtime"
    TaskData ||--o| ExecutorCheckpoint : "state"
    TaskData ||--o{ ExecutorHistory : "context"

    CoreCall ||--|| DataBase : "input_model"
    CoreCall ||--|| DataBase : "output_model"
    CoreCall ||--o| NodeInfo : "node"

    StepQueueItem {
        UUID step_id PK "步骤ID"
        Step step "步骤定义"
        bool enable_filling "是否启用填充"
        bool to_user "是否输出给用户"
    }

    Step {
        string name "步骤名称"
        string description "步骤描述"
        string type "步骤类型"
        string node "节点ID"
        dict params "用户参数"
    }

    NodeInfo {
        string id PK "节点ID"
        string callId "Call ID"
        string name "节点名称"
        dict knownParams "已知参数"
        dict overrideInput "输入覆盖"
        dict overrideOutput "输出覆盖"
    }

    ExecutorHistory {
        UUID taskId FK "任务ID"
        UUID stepId "步骤ID"
        string stepName "步骤名称"
        string stepType "步骤类型"
        StepStatus stepStatus "步骤状态"
        dict inputData "输入数据"
        dict outputData "输出数据"
    }

    CoreCall {
        string name "Call名称"
        string description "Call描述"
        bool enable_filling "启用填参"
        bool to_user "输出给用户"
        dict input "输入数据"
    }

    DataBase {
        dict properties "字段定义"
        dict json_schema "JSON Schema"
    }
```

### 6.2 步骤状态枚举

```mermaid
classDiagram
    class StepStatus {
        <<enumeration>>
        INIT 初始化
        WAITING 等待确认
        RUNNING 运行中
        SUCCESS 成功完成
        ERROR 执行错误
        PARAM 等待参数
        CANCELLED 用户取消
    }

    class StepType {
        <<enumeration>>
        START 开始节点
        END 结束节点
        AGENT 智能体节点
        LLM 大模型节点
        API API调用节点
        SQL 数据库节点
        CHOICE 条件分支节点
        LOOP 循环节点
    }
```

### 6.3 参数合并策略

```mermaid
flowchart LR
    A[node.knownParams] --> C{合并}
    B[step.params] --> C
    C --> D[最终参数]

    B -.->|优先级更高| C

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style D fill:#e7f5e1
```

**合并规则**：

```python
params = {}

# 1. 加载节点已知参数
if node and node.knownParams:
    params = node.knownParams.copy()

# 2. 用户参数覆盖
if step.params:
    params.update(step.params)

# 结果：用户参数 > 节点参数
```

### 6.4 输入输出流转

```mermaid
graph TB
    A[StepQueueItem] --> B[Step.params]
    C[NodeInfo] --> D[knownParams]

    B --> E[参数合并]
    D --> E

    E --> F[Call.instance]
    F --> G[Call._init]
    G --> H[Call.input]

    H --> I[_run_slot_filling]
    I --> J[Slot填充]
    J --> K[更新input]

    K --> L[Call._exec]
    L --> M[CallOutputChunk流]
    M --> N[_process_chunk]
    N --> O[最终输出]

    O --> P[ExecutorHistory.outputData]
    O --> Q[TaskRuntime.fullAnswer]

    style E fill:#fff4e1
    style J fill:#e7f5e1
    style N fill:#e1f5ff
```

## 7. Call 标准规范

### 7.1 Call 类必须实现的接口

```python
from typing import AsyncGenerator, Any
from pydantic import BaseModel

class CustomCallInput(DataBase):
    """自定义输入模型"""
    param1: str
    param2: int | None = None

class CustomCallOutput(DataBase):
    """自定义输出模型"""
    result: str
    status: str

class CustomCall(
    CoreCall,
    input_model=CustomCallInput,
    output_model=CustomCallOutput
):
    """自定义Call类"""

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的元信息"""
        return CallInfo(
            name="自定义Call",
            description="这是一个自定义的Call示例",
            input_schema=cls.input_model.model_json_schema(),
            output_schema=cls.output_model.model_json_schema()
        )

    async def _init(self, call_vars: CallVars) -> DataBase:
        """初始化，组装输入数据"""
        return CustomCallInput(
            param1=call_vars.question,
            param2=42
        )

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行，流式输出结果"""
        # 处理逻辑
        result = process_data(input_data)

        # 流式输出
        for chunk in result:
            yield CallOutputChunk(
                type=CallOutputType.TEXT,
                content=chunk
            )
```

### 7.2 Call 验证清单

```mermaid
flowchart TD
    Start([Call验证开始]) --> Check1{hasattr _init?}
    Check1 -->|否| Fail
    Check1 -->|是| Check2{callable _init?}
    Check2 -->|否| Fail
    Check2 -->|是| Check3{hasattr _exec?}
    Check3 -->|否| Fail
    Check3 -->|是| Check4{isasyncgenfunction _exec?}
    Check4 -->|否| Fail
    Check4 -->|是| Check5{hasattr info?}
    Check5 -->|否| Fail
    Check5 -->|是| Check6{callable info?}
    Check6 -->|否| Fail
    Check6 -->|是| Pass([验证通过])

    Fail([验证失败])

    style Pass fill:#e7f5e1
    style Fail fill:#ffe1e1
```

## 8. 特殊节点

### 8.1 特殊节点类型

```mermaid
graph TB
    A[SpecialCallType] --> B[EMPTY<br/>空节点]
    A --> C[SUMMARY<br/>总结节点]
    A --> D[FACTS<br/>事实提取]
    A --> E[SLOT<br/>参数填充]

    B -.-> B1[用于占位或跳过]
    C -.-> C1[生成对话总结]
    D -.-> D1[提取关键事实]
    E -.-> E1[自动填充参数]

    style A fill:#f9f,stroke:#333,stroke-width:4px
    style B fill:#e1f5ff
    style C fill:#fff4e1
    style D fill:#e7f5e1
    style E fill:#ffe1f5
```

### 8.2 特殊节点特性

| 节点类型 | Call ID | 用途 | 输入 | 输出 |
|---------|---------|------|------|------|
| Empty | `EMPTY` | 占位节点 | 任意 | 空 |
| Summary | `SUMMARY` | 总结生成 | 对话历史 | 总结文本 |
| FactsCall | `FACTS` | 事实提取 | 对话内容 | 事实列表 |
| Slot | `SLOT` | 参数填充 | Schema + 数据 | SlotOutput |

### 8.3 Slot 填充详解

**SlotOutput 结构**：

```python
class SlotOutput(BaseModel):
    slot_data: dict[str, Any]           # 已填充的参数数据
    remaining_schema: dict | None       # 仍然缺失的参数Schema
    filled_fields: list[str]            # 本次填充的字段
```

**使用场景**：

1. **自动填参** (`_run_slot_filling`)：
   - 在步骤执行前自动补充参数
   - 不存入历史记录
   - 填充结果更新到 `obj.input`

2. **手动填参** (用户补充)：
   - 步骤状态为 `PARAM` 时
   - 用户通过表单补充参数
   - 重新执行步骤

**填充策略**：

```mermaid
flowchart TD
    Start([开始填充]) --> GetSchema[获取input_model的Schema]
    GetSchema --> ApplyOverride[应用overrideInput]
    ApplyOverride --> CompareData[比对当前数据]

    CompareData --> HasData{字段有数据?}
    HasData -->|是| Skip[跳过该字段]
    HasData -->|否| TryFill{可以从上下文提取?}

    TryFill -->|是| Fill[填充该字段]
    TryFill -->|否| AddRemaining[添加到remaining_schema]

    Fill --> NextField{还有字段?}
    Skip --> NextField
    AddRemaining --> NextField

    NextField -->|是| HasData
    NextField -->|否| BuildOutput[构建SlotOutput]

    BuildOutput --> CheckRemaining{remaining_schema为空?}
    CheckRemaining -->|是| Complete([完全填充])
    CheckRemaining -->|否| Partial([部分填充])

    style Fill fill:#e7f5e1
    style Complete fill:#e7f5e1
    style Partial fill:#fff4e1
```

## 9. 错误处理

### 9.1 错误分类

```mermaid
graph TB
    A[步骤错误] --> B{错误阶段}

    B --> C[初始化错误]
    B --> D[执行错误]

    C --> C1[Node不存在]
    C --> C2[Call类不合法]
    C --> C3[实例化失败]

    D --> D1[CallError]
    D --> D2[通用异常]

    C1 -.-> E1[设置node=None<br/>尝试特殊节点]
    C2 -.-> E2[抛出ValueError<br/>终止步骤]
    C3 -.-> E3[记录日志<br/>重新抛出]

    D1 -.-> F1[提取message和data<br/>设置errorMessage<br/>状态=ERROR]
    D2 -.-> F2[记录堆栈<br/>设置errorMessage<br/>状态=ERROR]

    style C fill:#ffe1e1
    style D fill:#ffe1e1
```

### 9.2 错误处理策略

```python
# 初始化错误
try:
    self.obj = await call_cls.instance(self, self.node, **params)
except Exception:
    logger.exception("[StepExecutor] 初始化Call失败")
    raise  # 重新抛出，由上层处理

# 执行错误
try:
    content = await self._process_chunk(iterator, to_user=self.obj.to_user)
except Exception as e:
    logger.exception("[StepExecutor] 运行步骤失败，进行异常处理步骤")
    self.task.state.stepStatus = StepStatus.ERROR
    await self._push_message(EventType.STEP_OUTPUT.value, {})

    if isinstance(e, CallError):
        self.task.state.errorMessage = {
            "err_msg": e.message,
            "data": e.data,
        }
    else:
        self.task.state.errorMessage = {
            "data": {},
        }
    return  # 不抛出异常，步骤结束
```

### 9.3 错误信息结构

```python
# CallError
{
    "err_msg": "具体的错误描述",
    "data": {
        "error_type": "parameter_missing",
        "missing_fields": ["field1", "field2"],
        "details": "..."
    }
}

# 通用错误
{
    "data": {}  # 空字典
}
```

## 10. 性能优化

### 10.1 流式处理

**优势**：

- 减少内存占用
- 提升用户体验（实时反馈）
- 支持超长输出

**实现**：

```python
async def _process_chunk(
    self,
    iterator: AsyncGenerator[CallOutputChunk, None],
    *,
    to_user: bool = False,
) -> str | dict[str, Any]:
    content: str | dict[str, Any] = ""

    async for chunk in iterator:
        # 边接收边处理
        if isinstance(chunk.content, str):
            content += chunk.content
            if to_user:
                # 立即推送，不等待完整输出
                await self._push_message(EventType.TEXT_ADD.value, chunk.content)

    return content
```

### 10.2 参数合并优化

**策略**：

- 延迟合并：在实例化时才合并
- 浅拷贝：避免深拷贝带来的性能损耗
- 增量更新：Slot 填充时使用 `update` 而非重建

```python
# 高效合并
params = node.knownParams if node and node.knownParams else {}
if step.params:
    params.update(step.params)  # 原地更新

# Slot更新
self.obj.input.update(result.slot_data)  # 增量更新
```

### 10.3 状态缓存

**避免重复查询**：

```python
# 缓存Node信息
self.node = await NodeManager.get_node(node_id)

# 缓存Call类
self.obj = await call_cls.instance(...)

# 避免在循环中重复获取状态
state = self.task.state  # 缓存引用
if not state:
    raise RuntimeError(...)
state.stepStatus = StepStatus.RUNNING
```

## 11. 参考资料

### 11.1 相关模块

- [BaseExecutor](base.py) - 执行器基类
- [CoreCall](../call/core.py) - Call 基类
- [Slot](../call/slot/slot.py) - 参数填充
- [NodeManager](../../services/node.py) - 节点管理
- [Call Pool](../pool/pool.py) - Call 池

### 11.2 数据模型

- [ExecutorHistory](../../models/task.py) - 执行历史
- [ExecutorCheckpoint](../../models/task.py) - 执行检查点
- [StepStatus](../../models/task.py) - 步骤状态枚举
- [StepType](../../models/task.py) - 步骤类型枚举

### 11.3 消息队列

- [MessageQueue](../../common/queue.py) - 消息队列
- [EventType](../../schemas/enum_var.py) - 事件类型枚举
