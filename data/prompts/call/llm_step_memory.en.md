{% if role == "user" %}
# Task Execution Record - Step {{ step_index }}

## Task Goal

{{ step_goal }}

## Tool Invocation

To complete this step, we invoked the tool `{{ step_name }}`.

## Input Parameters

The parameters provided to the tool are:

```json
{{ input_data | tojson(ensure_ascii=False, indent=2) }}
```

{% elif role == "assistant" %}
# Task Execution Result - Step {{ step_index }}

## Execution Status

Step {{ step_index }} has been completed.

Execution status: {{ step_status }}

## Output Data

The data obtained from the tool execution is:

```json
{{ output_data | tojson(ensure_ascii=False, indent=2) }}
```

This data will be used as input or reference information for subsequent steps.

{% endif %}
