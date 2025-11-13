该插件包样例为EulerCopilot本地数据文件夹内semantics/子文件夹的目录结构与示例。

结构定义如下：

```text
- semantics/
| - app/                   # 应用相关数据
| | - test_app/            # 样例应用
| | | - metadata.yaml      # 应用的元数据
| | | - icon.png           # 应用的图标
| | | - flow/              # 应用中的工作流信息
| | | | - test.yaml        # 样例工作流
| - service/               # 语义接口&MCP相关数据（服务）
| | - test_service/        # 样例服务
| | | - metadata.yaml      # 服务的元数据
| | | - mcp-config.json    # MCP服务的配置
| | | - openapi/           # API相关信息
| | | | - api.yaml         # 样例API文件
| | | - mcp/               # MCP程序文件夹
```