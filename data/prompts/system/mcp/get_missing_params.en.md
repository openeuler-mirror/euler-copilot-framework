Based on tool execution errors, identify missing or incorrect parameters, set them to null, and retain correct parameter values.
**Please call the `get_missing_parameters` tool to return the result**.

## Task Requirements
- **Analyze error messages**: Identify which parameters caused the error
- **Mark problematic parameters**: Set missing or incorrect parameter values to `null`
- **Retain valid values**: Keep original values for parameters that didn't cause errors
- **Call tool to return**: Must call the `get_missing_parameters` tool with the parameter JSON as input

## Example

**Tool**: `mysql_analyzer` - Analyze MySQL database performance

**Current Input**:
```json
{"host": "192.0.0.1", "port": 3306, "username": "root", "password": "password"}
```

**Parameter Schema**:
```json
{
  "properties": {
    "host": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Host address"},
    "port": {"anyOf": [{"type": "integer"}, {"type": "null"}], "description": "Port number"},
    "username": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Username"},
    "password": {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "Password"}
  },
  "required": ["host", "port", "username", "password"]
}
```

**Error**: `password is not correct`

**Should call tool**:
```
get_missing_parameters({"host": "192.0.0.1", "port": 3306, "username": null, "password": null})
```

> Analysis: Error indicates incorrect password, so set `password` to `null`; also set `username` to `null` for user to provide credentials again

---

## Current Task

**Tool**: `{{tool_name}}` - {{tool_description}}

**Current Input**:
```json
{{input_param}}
```

**Parameter Schema**:
```json
{{input_schema}}
```

**Error**: {{error_message}}

**Please call the `get_missing_parameters` tool to return the analysis result**.
