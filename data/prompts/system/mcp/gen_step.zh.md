# 步骤规划任务

## 任务说明

你需要根据前面的思考分析和用户目标，立即调用 `create_next_step` 函数来规划下一个执行步骤。

**重要**: 你必须调用函数，不要只是描述或说明，而是实际执行函数调用。

## 函数定义

### 函数名称

`{{function_schema['name']}}`

### 函数描述

{{function_schema['description']}}

### JSON Schema

```json
{{function_schema | tojson(indent=2)}}
```

### 参数详细说明

#### 1. tool_name (必填)

- **类型**: string
- **约束**: 必须是以下枚举值之一
  {% for tool in tools %}
  - `"{{tool.toolName}}"` - {{tool.description}}
  {% endfor %}
  - `"Final"` - 当用户目标已完成时使用
- **说明**: 从可用工具列表中选择最适合当前步骤的工具名称

#### 2. description (必填)

- **类型**: string
- **说明**: 清晰描述本步骤要执行的具体操作内容
- **要求**:
  - 说明选择该工具的原因
  - 描述具体要完成什么任务
  - 简洁明确，通常1-2句话

## 调用要求

✓ **必须调用函数**: 不要只描述，要实际调用 `create_next_step` 函数
✓ **函数名固定**: 函数名必须是 `create_next_step`，不是工具名
✓ **tool_name 精确匹配**: tool_name 的值必须完全匹配枚举列表中的某个值
✓ **参数完整**: tool_name 和 description 两个参数都必须提供
✓ **基于思考结论**: 根据前面的思考分析选择最合适的工具

{% raw %}{% if use_xml_format %}{% endraw %}

## XML 格式调用示例

当使用 XML 格式时，请按以下格式调用：

```xml
<create_next_step>
<tool_name>mysql_analyzer</tool_name>
<description>获取数据库的慢查询日志和性能指标，以分析性能瓶颈</description>
</create_next_step>
```

**注意**:

- tool_name 的值必须严格匹配可用工具列表中的工具名称
- 如果任务已完成，tool_name 设置为 `Final`

{% raw %}{% endif %}{% endraw %}

## 执行指令

**用户目标**: {{goal}}

基于上面的思考分析，现在立即调用 `create_next_step` 函数，选择最合适的工具并规划下一步操作。
