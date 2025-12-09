#!/bin/bash

# RAG 服务部署脚本

# 设置路径
RAG_DIR="/usr/lib/sysagent/mcp_center/servers/rag"
SERVICE_FILE="/usr/lib/sysagent/mcp_center/service/rag.service"

# 复制 service 文件
if [ -f "$SERVICE_FILE" ]; then
    cp "$SERVICE_FILE" /etc/systemd/system/
    echo "✅ Service 文件已复制"
else
    echo "⚠️  警告：未找到 service 文件：$SERVICE_FILE"
fi

# 安装依赖
if [ -f "$RAG_DIR/src/requirements.txt" ]; then
    python3 -m pip install -r "$RAG_DIR/src/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo "✅ 依赖安装完成"
fi

# 重新加载 systemd
systemctl daemon-reload

# 启用服务
systemctl enable rag.service
echo "✅ 服务已启用"

# 启动服务
systemctl start rag.service
echo "✅ 服务已启动"

# 查看服务状态
systemctl status rag.service

# 设置 CLI 工具权限并创建符号链接
chmod +x "$RAG_DIR/src/cli.py"
rm -f /usr/local/bin/rag-server
ln -s "$RAG_DIR/src/cli.py" /usr/local/bin/rag-server
echo "✅ CLI 工具已安装：rag-server"

echo ""
echo "安装完成！可以使用以下命令："
echo "  rag-server --help          # 查看帮助"
echo "  rag-server list_kb         # 列出知识库"
echo "  rag-server import_doc --file_paths /path/to/file.txt  # 导入文档"

