#!/bin/bash

SERVICE_DIR="/usr/lib/sysagent/mcp_center/service"
SYSTEMD_TARGET_DIR="/etc/systemd/system"

# 添加可执行权限并运行 oe_cli_mcp_server 脚本
chmod +x /usr/lib/sysagent/mcp_center/oe_cli_mcp_server/run.sh
if ! /usr/lib/sysagent/mcp_center/oe_cli_mcp_server/run.sh; then
    echo "错误: oe_cli_mcp_server/run.sh 执行失败，退出码: $?" >&2
fi

# 添加可执行权限并运行 rag 脚本
chmod +x /usr/lib/sysagent/mcp_center/third_party_mcp/rag/run.sh
if ! /usr/lib/sysagent/mcp_center/third_party_mcp/rag/run.sh; then
    echo "错误: rag/run.sh 执行失败，退出码: $?" >&2
fi

systemctl daemon-reload

for service_file in "$SERVICE_DIR"/*.service; do
  # 只保留「文件存在」的核心判断，其他验证全删
  if [ -f "$service_file" ]; then
    service_name=$(basename "$service_file" .service)
    dest_service="$SYSTEMD_TARGET_DIR/$service_name.service"
    echo "正在载入service: $dest_service"
    # 直接复制（-f 强制覆盖已存在的文件，-a 保留权限）
    cp -af "$service_file" "$dest_service"

    # 原有的启用和启动命令
    systemctl enable "$service_name"
    systemctl start "$service_name"
  fi
done

chmod +x /usr/lib/sysagent/mcp_center/util/cli.py
rm -f /usr/local/bin/mcp-manager
ln -s /usr/lib/sysagent/mcp_center/util/cli.py /usr/local/bin/mcp-manager

