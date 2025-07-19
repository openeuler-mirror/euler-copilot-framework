# 工作流变量管理系统

## 概述

工作流变量管理系统为Euler Copilot Framework提供了全面的变量管理功能，支持在工作流执行过程中进行变量的定义、存储、解析和使用。

## 功能特性

### 1. 多种变量类型支持
- **基础类型**: String、Number、Boolean、Object、File
- **安全类型**: Secret（加密存储的密钥变量）  
- **数组类型**: Array[Any]、Array[String]、Array[Number]、Array[Object]、Array[File]、Array[Boolean]、Array[Secret]

### 2. 四种作用域
- **系统级变量** (`system`): 只读，包含query、files、app_id等系统信息
- **用户级变量** (`user`): 跟随用户，如个人API密钥、配置信息
- **环境级变量** (`env`): 跟随工作流，如流程配置参数
- **对话级变量** (`conversation`): 单次对话内有效，支持局部作用域

### 3. 变量解析语法
支持在模板中使用以下语法引用变量：
```
{{sys.query}}              # 系统变量
{{user.api_key}}           # 用户变量
{{env.config.timeout}}     # 环境变量（支持嵌套访问）
{{conversation.result}}    # 对话变量
```

### 4. 安全保障
- Secret变量加密存储
- 访问权限控制
- 审计日志记录
- 访问频率限制
- 密钥强度检查

## API 接口

### 变量管理
- `POST /api/variable/create` - 创建变量
- `PUT /api/variable/update` - 更新变量值
- `DELETE /api/variable/delete` - 删除变量
- `GET /api/variable/get` - 获取单个变量
- `GET /api/variable/list` - 列出变量

### 模板解析
- `POST /api/variable/parse` - 解析模板中的变量引用
- `POST /api/variable/validate` - 验证模板中的变量引用

### 系统信息
- `GET /api/variable/types` - 获取支持的变量类型
- `POST /api/variable/clear-conversation` - 清空对话变量

## 使用示例

### 1. 创建用户级变量
```json
{
  "name": "openai_api_key",
  "var_type": "secret",
  "scope": "user",
  "value": "sk-xxxxxxxxxxxxxxxx",
  "description": "OpenAI API密钥"
}
```

### 2. 在工作流中使用变量
```yaml
steps:
  llm_call:
    node: "llm"
    params:
      system_prompt: "你是一个助手，用户查询：{{sys.query}}"
      api_key: "{{user.openai_api_key}}"
      temperature: "{{env.llm_config.temperature}}"
```

### 3. 在对话中设置临时变量
工作流执行过程中可以动态设置对话级变量：
```python
await VariableIntegration.add_conversation_variable(
    name="processing_result",
    value={"status": "completed", "data": result},
    conversation_id=conversation_id,
    var_type_str="object"
)
```

## 集成到工作流

系统自动集成到现有的工作流调度器中：

1. **系统变量自动初始化** - 每次工作流启动时自动设置系统变量
2. **输入参数解析** - Call的输入参数自动解析变量引用
3. **模板渲染** - LLM提示词等模板自动替换变量
4. **输出变量提取** - 步骤输出可自动提取为对话级变量

## 安全机制

### Secret变量保护
- 使用AES加密存储
- 基于用户ID和变量名生成唯一加密密钥
- 显示时自动打码
- 支持密钥轮换

### 访问控制
- 权限验证（用户只能访问自己的变量）
- 访问频率限制（防止暴力破解）
- IP地址验证（可选）
- 失败尝试监控和临时封禁

### 审计日志
- 完整的访问日志记录
- 密钥访问审计（记录哈希值而非原始值）
- 自动清理过期日志

## 开发指南

### 添加新的变量类型
1. 在`VariableType`枚举中添加新类型
2. 创建继承自`BaseVariable`的新变量类
3. 在`VARIABLE_CLASS_MAP`中注册映射关系

### 扩展变量解析
1. 修改`VariableParser.VARIABLE_PATTERN`正则表达式
2. 在`resolve_variable_reference`方法中添加新的解析逻辑

### 自定义安全策略
1. 继承`SecretVariableSecurity`类
2. 重写相关的安全检查方法
3. 在应用启动时注册自定义安全管理器

## 故障排除

### 常见问题
1. **变量解析失败** - 检查变量名是否存在，作用域是否正确
2. **Secret变量解密失败** - 可能是加密密钥损坏，需要重新设置
3. **访问被拒绝** - 检查用户权限和访问频率限制

### 日志调试
启用DEBUG日志级别查看详细的变量解析过程：
```python
import logging
logging.getLogger('apps.scheduler.variable').setLevel(logging.DEBUG)
```

## 最佳实践

1. **变量命名** - 使用描述性的名称，避免特殊字符
2. **作用域选择** - 根据变量的生命周期选择合适的作用域
3. **Secret管理** - 定期轮换密钥，使用强密码
4. **性能优化** - 避免在循环中频繁解析变量
5. **安全审计** - 定期检查访问日志，监控异常行为 