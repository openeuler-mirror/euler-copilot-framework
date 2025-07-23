# 变量池架构文档

## 架构设计

基于用户需求，变量系统采用"模板-实例"的两级架构：

### 设计理念

- **Flow级别（父pool）**：管理变量模板定义，用户可以查看和配置变量结构
- **Conversation级别（子pool）**：管理变量实例，存储实际的运行时数据

### 变量分类

不同类型的变量有不同的存储和管理方式：
- **系统变量**：模板在Flow级别定义，实例在Conversation级别运行时更新
- **对话变量**：模板在Flow级别定义，实例在Conversation级别用户可设置
- **环境变量**：直接在Flow级别存储和使用
- **用户变量**：在User级别长期存储

## 架构实现

### 变量池类型

#### 1. UserVariablePool（用户变量池）
- **关联ID**: `user_id`
- **权限**: 用户可读写
- **生命周期**: 随用户创建而创建，长期存在
- **典型变量**: API密钥、用户偏好、个人配置等

#### 2. FlowVariablePool（流程变量池）
- **关联ID**: `flow_id`
- **权限**: 流程可读写
- **生命周期**: 随 flow 创建而创建
- **继承**: 支持从父流程继承
- **存储内容**: 
  - 环境变量（直接使用）
  - 系统变量模板（供对话继承）
  - 对话变量模板（供对话继承）

#### 3. ConversationVariablePool（对话变量池）
- **关联ID**: `conversation_id`
- **权限**: 
  - 系统变量实例：只读，由系统自动更新
  - 对话变量实例：可读写，用户可设置值
- **生命周期**: 随对话创建而创建，对话结束后可选择性清理
- **初始化方式**: 从FlowVariablePool的模板自动继承
- **包含内容**:
  - **系统变量实例**：`query`, `files`, `dialogue_count`等运行时值
  - **对话变量实例**：用户定义的对话上下文数据

## 核心设计原则

### 1. 统一的对话上下文
所有对话相关的变量（无论是系统变量还是对话变量）都在同一个对话变量池中管理，确保上下文的一致性。

### 2. 权限区分
通过 `is_system` 标记区分系统变量和对话变量：
- `is_system=True`: 系统变量，只读，由系统自动更新
- `is_system=False`: 对话变量，可读写，支持人为修改

### 3. 自动初始化和持久化
创建对话变量池时，自动初始化所有必需的系统变量，设置合理的默认值，并立即持久化到数据库，确保系统变量在任何时候都可用。

## 使用方式

### 1. 创建对话变量池

```python
pool_manager = await get_pool_manager()

# 创建对话变量池（自动包含系统变量）
conv_pool = await pool_manager.create_conversation_pool("conv123", "flow456")
```

### 2. 更新系统变量

```python
# 系统变量由解析器自动更新
parser = VariableParser(
    user_id="user123",
    flow_id="flow456", 
    conversation_id="conv123"
)

# 更新系统变量
await parser.update_system_variables({
    "question": "你好，请帮我分析数据",
    "files": [{"name": "data.csv", "size": 1024}],
    "dialogue_count": 1,
    "user_sub": "user123"
})
```

### 3. 更新对话变量

```python
# 添加对话变量
await conv_pool.add_variable(
    name="context_history",
    var_type=VariableType.ARRAY_STRING,
    value=["用户问候", "系统回应"],
    description="对话历史"
)

# 更新对话变量
await conv_pool.update_variable("context_history", value=["问候", "回应", "新消息"])
```

### 4. 变量解析

```python
# 系统变量和对话变量使用相同的引用语法
template = """
系统变量 - 用户查询: {{sys.query}}
系统变量 - 对话轮数: {{sys.dialogue_count}}
对话变量 - 历史: {{conversation.context_history}}
用户变量 - 偏好: {{user.preferences}}
环境变量 - 数据库: {{env.database_url}}
"""

parsed = await parser.parse_template(template)
```

## 变量引用语法

变量引用保持不变：
- `{{sys.variable_name}}` - 系统变量（对话级别，只读）
- `{{conversation.variable_name}}` - 对话变量（对话级别，可读写）
- `{{user.variable_name}}` - 用户变量
- `{{env.variable_name}}` - 环境变量

## 权限控制详细说明

### 系统变量权限
```python
# 普通更新会被拒绝
await conv_pool.update_variable("query", value="new query")  # ❌ 抛出 PermissionError

# 系统内部更新
await conv_pool.update_system_variable("query", "new query")  # ✅ 成功
# 或者
await conv_pool.update_variable("query", value="new query", force_system_update=True)  # ✅ 成功
```

### 对话变量权限
```python
# 普通对话变量可以自由更新
await conv_pool.update_variable("context_history", value=new_history)  # ✅ 成功
```

## 数据存储

### 元数据增强
```python
class VariableMetadata(BaseModel):
    # ... 其他字段
    is_system: bool = Field(default=False, description="是否为系统变量（只读）")
```

### 数据库查询
系统变量和对话变量存储在同一个集合中，通过 `metadata.is_system` 字段区分。

## 迁移影响

### 对用户的影响
- ✅ **变量引用语法完全不变**
- ✅ **API接口完全兼容**
- ✅ **现有功能正常工作**

### 内部实现变化
- 去掉了独立的 `SystemVariablePool`
- 系统变量现在在 `ConversationVariablePool` 中管理
- 通过权限控制区分系统变量和对话变量

## 架构优势

### 1. 逻辑一致性
系统变量和对话变量都属于对话上下文，在同一个池中管理更合理。

### 2. 简化管理
不需要在系统池和对话池之间同步数据，避免了数据一致性问题。

### 3. 更好的性能
减少了池之间的数据传递和同步开销。

### 4. 扩展性
为未来可能的对话级系统变量扩展提供了更好的基础。

## 总结

修正后的架构更准确地反映了变量的实际使用场景：
- **用户变量**: 用户级别，长期存在
- **环境变量**: 流程级别，配置相关
- **系统变量 + 对话变量**: 对话级别，上下文相关

这样的设计更符合实际业务逻辑，也更容易理解和维护。

## 系统变量详细说明

### 预定义系统变量

每个对话变量池创建时，会自动初始化以下系统变量：

| 变量名 | 类型 | 描述 | 初始值 |
|-------|------|------|--------|
| `query` | STRING | 用户查询内容 | "" |
| `files` | ARRAY_FILE | 用户上传的文件列表 | [] |
| `dialogue_count` | NUMBER | 对话轮数 | 0 |
| `app_id` | STRING | 应用ID | "" |
| `flow_id` | STRING | 工作流ID | {flow_id} |
| `user_id` | STRING | 用户ID | "" |
| `session_id` | STRING | 会话ID | "" |
| `conversation_id` | STRING | 对话ID | {conversation_id} |
| `timestamp` | NUMBER | 当前时间戳 | {当前时间} |

### 系统变量生命周期

1. **创建阶段**：对话变量池创建时，所有系统变量被初始化并持久化到数据库
2. **更新阶段**：通过`VariableParser.update_system_variables()`方法更新系统变量值
3. **访问阶段**：通过模板解析或直接访问获取系统变量值
4. **清理阶段**：对话结束时，整个对话变量池被清理

### 系统变量更新机制

```python
# 创建解析器并确保对话池存在
parser = VariableParser(user_id=user_id, flow_id=flow_id, conversation_id=conversation_id)
await parser.create_conversation_pool_if_needed()

# 更新系统变量
context = {
    "question": "用户的问题",
    "files": [{"name": "file.txt", "size": 1024}],
    "dialogue_count": 1,
    "app_id": "app123",
    "user_sub": user_id,
    "session_id": "session456"
}

await parser.update_system_variables(context)
```

### 系统变量的只读保护

```python
# ❌ 直接修改系统变量会失败
await conversation_pool.update_variable("query", value="修改内容")  # 抛出PermissionError

# ✅ 只能通过系统内部接口更新
await conversation_pool.update_system_variable("query", "新内容")  # 成功
```

### 使用系统变量

```python
# 在模板中引用系统变量
template = """
用户问题：{{sys.query}}
对话轮数：{{sys.dialogue_count}}
工作流ID：{{sys.flow_id}}
"""

parsed = await parser.parse_template(template)
``` 