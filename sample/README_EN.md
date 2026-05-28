The following is an example of the directory structure and content of the **semantics/** subfolder in the local data folder of openEuler Intelligence.

The structure is defined as follows:

```text
- semantics/
| - app/                   # Application-related data
| | - test_app/            # Sample application
| | | - metadata.yaml      # Application metadata
| | | - icon.png           # Application icon
| | | - flow/              # Workflow information in the application
| | | | - test.yaml        # Sample workflow
| - call/                  # Data related to custom Python tools
| | - __init__.py
| | - test_call/           # Sample user tool
| | | - __init__.py
| | | - user_tool.py       # Python tool code
| - service/               # Semantic API & MCP-related data (service)
| | - test_service/        # Sample service
| | | - metadata.yaml      # Service metadata
| | | - mcp-config.json    # MCP service configuration
| | | - openapi/           # API information
| | | | - api.yaml         # Sample API file
| | | - mcp/               # MCP program folder
```
