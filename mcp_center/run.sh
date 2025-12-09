#!/bin/bash

SERVICE_DIR="/usr/lib/sysagent/mcp_center/service"
SYSTEMD_TARGET_DIR="/etc/systemd/system"
/usr/lib/sysagent/mcp_center/servers/oe_cli_mcp_server/run.sh
/usr/lib/sysagent/mcp_center/servers/rag/run.sh

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

pip install -r /usr/lib/sysagent/mcp_center/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
