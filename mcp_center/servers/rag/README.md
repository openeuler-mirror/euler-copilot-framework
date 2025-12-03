# RAG知识库管理MCP（管理控制程序）规范文档

## 一、服务介绍

本服务是一款功能完整的RAG（检索增强生成）知识库管理MCP（管理控制程序），基于SQLite数据库、FTS5全文检索、sqlite-vec向量检索等技术，实现对知识库的**创建、删除、选择、文档导入、混合检索、文档管理、数据库导入导出**等全生命周期管理功能。支持TXT、DOCX、DOC、PDF等多种文档格式，采用异步批量向量化处理，结合关键词检索和向量检索的混合搜索策略，为知识库构建和智能检索提供完整的解决方案，适配中文与英文双语言配置，满足不同场景下的使用需求。


## 二、核心工具信息

| 工具名称 | 工具功能 | 核心输入参数 | 关键返回内容 |
| ---- | ---- | ---- | ---- |
| `create_knowledge_base` | 创建一个新的知识库，知识库是文档的容器，每个知识库可以有自己的chunk_size和embedding配置 | - `kb_name`：知识库名称（必填，必须唯一）<br>- `chunk_size`：chunk大小，单位token（必填，例如512、1024）<br>- `embedding_model`：向量化模型名称（可选）<br>- `embedding_endpoint`：向量化服务端点URL（可选）<br>- `embedding_api_key`：向量化服务API Key（可选） | 创建结果字典（含`kb_id`知识库ID、`kb_name`知识库名称、`chunk_size`chunk大小） |
| `delete_knowledge_base` | 删除指定的知识库，不能删除当前正在使用的知识库，删除知识库会级联删除该知识库下的所有文档和chunks | - `kb_name`：知识库名称（必填） | 删除结果字典（含`kb_name`已删除的知识库名称） |
| `list_knowledge_bases` | 列出所有可用的知识库，返回所有知识库的详细信息，包括当前选中的知识库 | 无参数 | 知识库列表字典（含`knowledge_bases`知识库列表、`count`知识库数量、`current_kb_id`当前选中的知识库ID，每个知识库包含id、name、chunk_size、embedding_model、created_at、is_current等字段） |
| `select_knowledge_base` | 选择一个知识库作为当前使用的知识库，选择后，后续的文档导入、查询等操作都会在该知识库中进行 | - `kb_name`：知识库名称（必填） | 选择结果字典（含`kb_id`知识库ID、`kb_name`知识库名称、`document_count`该知识库下的文档数量） |
| `import_document` | 导入文档到当前选中的知识库，支持多文件并发导入，支持TXT、DOCX、DOC、PDF格式，文档会被解析、切分为chunks，并异步批量生成向量存储到数据库中 | - `file_paths`：文件路径列表（绝对路径），支持1~n个文件，为list形式（必填）<br>- `chunk_size`：chunk大小，单位token（可选，默认使用知识库的chunk_size） | 导入结果字典（含`total`总文件数、`success_count`成功导入的文件数、`failed_count`失败的文件数、`success_files`成功导入的文件列表、`failed_files`失败的文件列表） |
| `search` | 在当前选中的知识库中进行混合检索，结合关键词检索（FTS5）和向量检索（sqlite-vec），使用加权方式合并结果（关键词权重0.3，向量权重0.7），去重后使用Jaccard相似度重排序，返回最相关的top-k个结果 | - `query`：查询文本（必填）<br>- `top_k`：返回数量（可选，默认从配置读取，通常为5） | 检索结果字典（含`chunks`chunk列表、`count`结果数量，每个chunk包含id、doc_id、content、tokens、chunk_index、doc_name、score等字段） |
| `list_documents` | 查看当前选中的知识库下的所有文档列表，返回文档的详细信息 | 无参数 | 文档列表字典（含`documents`文档列表、`count`文档数量，每个文档包含id、name、file_path、file_type、chunk_size、created_at、updated_at等字段） |
| `delete_document` | 删除当前选中的知识库下的指定文档，删除文档会级联删除该文档的所有chunks | - `doc_name`：文档名称（必填） | 删除结果字典（含`doc_name`已删除的文档名称） |
| `update_document` | 修改文档的chunk_size并重新解析文档，会删除原有的chunks，使用新的chunk_size重新切分文档，并异步批量生成新的向量 | - `doc_name`：文档名称（必填）<br>- `chunk_size`：新的chunk大小，单位token（必填） | 修改结果字典（含`doc_id`文档ID、`doc_name`文档名称、`chunk_count`新的chunk数量、`chunk_size`新的chunk大小） |
| `export_database` | 导出整个kb.db数据库文件到指定路径 | - `export_path`：导出路径（绝对路径，必填） | 导出结果字典（含`source_path`源数据库路径、`export_path`导出路径） |
| `import_database` | 导入一个.db数据库文件，将其中的内容合并到kb.db中，导入时会自动处理重名冲突，为知识库和文档名称添加时间戳 | - `source_db_path`：源数据库文件路径（绝对路径，必填） | 导入结果字典（含`source_path`源数据库路径、`imported_kb_count`导入的知识库数量、`imported_doc_count`导入的文档数量） |

