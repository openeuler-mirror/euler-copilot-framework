## Task Description

You are an expert MCP (Model Context Protocol) selector.
Your task is to analyze the reasoning result and select the most appropriate MCP server ID.

## Reasoning Result

Below is the reasoning result that needs to be analyzed:

```
{{ reasoning_result }}
```

## Available MCP Servers

List of available MCP server IDs:

{% for mcp_id in mcp_ids %}
- `{{ mcp_id }}`
{% endfor %}

## Selection Requirements

Please analyze the reasoning result carefully and select the MCP server that best matches the requirements. Focus on:

1. **Capability Matching**: Align the capability requirements described in the reasoning with the MCP server functions
2. **Scenario Fit**: Ensure the MCP server is suitable for the current application scenario
3. **Optimal Choice**: Select the most appropriate server ID from the available list

## Output Format

Please use the `select_mcp` tool to make your selection by providing the chosen MCP server ID.
