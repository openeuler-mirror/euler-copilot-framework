# 变量存储格式配置说明

## 概述

节点执行完成后，系统会根据节点的`output_parameters`配置自动将输出数据保存到对话变量池中。变量的存储格式有两种：

1. **直接格式**: `conversation.key`
2. **带前缀格式**: `conversation.step_id.key`

## 配置方式

### 1. 通过节点类型配置

在 `apps/scheduler/executor/step_config.py` 中的 `DIRECT_CONVERSATION_VARIABLE_NODE_TYPES` 集合中添加节点类型：

```python
DIRECT_CONVERSATION_VARIABLE_NODE_TYPES: Set[str] = {
    "Start",        # Start节点
    "Input",        # 输入节点
    "YourNewNode",  # 新增的节点类型
}
```

### 2. 通过名称模式配置

在 `DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS` 集合中添加匹配模式：

```python
DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS: Set[str] = {
    "start",    # 匹配以"start"开头的节点名称
    "init",     # 匹配以"init"开头的节点名称
    "config",   # 新增：匹配以"config"开头的节点名称
}
```

## 判断逻辑

系统会按以下顺序判断是否使用直接格式：

1. 检查节点的 `call_id` 是否在 `DIRECT_CONVERSATION_VARIABLE_NODE_TYPES` 中
2. 检查节点的 `step_name` 是否在 `DIRECT_CONVERSATION_VARIABLE_NODE_TYPES` 中  
3. 检查节点名称（小写）是否以 `DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS` 中的模式开头
4. 检查 `step_id`（小写）是否以 `DIRECT_CONVERSATION_VARIABLE_NAME_PATTERNS` 中的模式开头

如果任一条件满足，则使用直接格式 `conversation.key`，否则使用带前缀格式 `conversation.step_id.key`。

## 使用示例

### 示例1：Start节点

```json
// 节点配置
{
  "call_id": "Start",
  "step_name": "start",
  "step_id": "start_001",
  "output_parameters": {
    "user_name": {"type": "string"},
    "session_id": {"type": "string"}
  }
}

// 保存的变量格式
conversation.user_name = "张三"
conversation.session_id = "sess_123"
```

### 示例2：普通处理节点

```json
// 节点配置  
{
  "call_id": "Code",
  "step_name": "数据处理",
  "step_id": "process_001", 
  "output_parameters": {
    "result": {"type": "object"},
    "status": {"type": "string"}
  }
}

// 保存的变量格式
conversation.process_001.result = {...}
conversation.process_001.status = "success"
```

### 示例3：配置节点（新增类型）

```python
# 在step_config.py中添加
DIRECT_CONVERSATION_VARIABLE_NODE_TYPES.add("GlobalConfig")
```

```json
// 节点配置
{
  "call_id": "GlobalConfig", 
  "step_name": "全局配置",
  "step_id": "config_001",
  "output_parameters": {
    "api_key": {"type": "secret"},
    "timeout": {"type": "number"}
  }
}

// 保存的变量格式（使用直接格式）
conversation.api_key = "xxx"
conversation.timeout = 30
```

## 变量引用

在其他节点中可以通过以下方式引用这些变量：

```json
{
  "input_parameters": {
    "user": {
      "reference": "{{conversation.user_name}}"  // 直接格式变量
    },
    "data": {
      "reference": "{{conversation.process_001.result}}"  // 带前缀格式变量
    }
  }
}
```

## 注意事项

1. **一致性**: 建议同时添加大小写版本以确保兼容性
2. **命名冲突**: 使用直接格式时需要注意变量名冲突问题
3. **可追溯性**: 带前缀格式便于追踪变量来源，直接格式便于全局访问
4. **配置变更**: 修改配置后需要重启服务才能生效 