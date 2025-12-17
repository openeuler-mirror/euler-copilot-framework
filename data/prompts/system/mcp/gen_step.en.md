# Step Planning Task

## Task Description

You need to immediately call the `create_next_step` function to plan the next execution step based on the previous thinking analysis and user goal.

**Important**: You must call the function, not just describe or explain, but actually execute the function call.

## Function Definition

### Function Name

`{{function_schema['name']}}`

### Function Description

{{function_schema['description']}}

### JSON Schema

```json
{{function_schema | tojson(indent=2)}}
```

### Parameter Details

#### 1. tool_name (required)

- **Type**: string
- **Constraint**: Must be one of the following enum values
  {% for tool in tools %}
  - `"{{tool.toolName}}"` - {{tool.description}}
  {% endfor %}
  - `"Final"` - Use when the user goal is completed
- **Description**: Select the most appropriate tool name from the available tools list for the current step

#### 2. description (required)

- **Type**: string
- **Description**: Clearly describe the specific operation to be performed in this step
- **Requirements**:
  - Explain why this tool is chosen
  - Describe what task needs to be completed
  - Be concise and clear, typically 1-2 sentences

## Calling Requirements

✓ **Must call the function**: Don't just describe, actually call the `create_next_step` function
✓ **Fixed function name**: The function name must be `create_next_step`, not the tool name
✓ **tool_name exact match**: The tool_name value must exactly match one of the enum values
✓ **Complete parameters**: Both tool_name and description parameters must be provided
✓ **Based on thinking conclusion**: Select the most appropriate tool based on the previous thinking analysis

{% raw %}{% if use_xml_format %}{% endraw %}

## XML Format Call Example

When using XML format, please call in the following format:

```xml
<create_next_step>
<tool_name>mysql_analyzer</tool_name>
<description>Retrieve slow query logs and performance metrics from the database to analyze performance bottlenecks</description>
</create_next_step>
```

**Note**:

- The tool_name value must strictly match a tool name from the available tools list
- If the task is completed, set tool_name to `Final`

{% raw %}{% endif %}{% endraw %}

## Execution Instruction

**User Goal**: {{goal}}

Based on the thinking and analysis above, immediately call the `create_next_step` function now, select the most appropriate tool and plan the next operation.
