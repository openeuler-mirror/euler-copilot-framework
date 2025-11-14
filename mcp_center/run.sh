#!/bin/bash

SERVICE_DIR="/usr/lib/euler-copilot-framework/mcp_center/service"

for service_file in "$SERVICE_DIR"/*.service; do
  if [ -f "$service_file" ]; then
    service_name=$(basename "$service_file" .service)
    systemctl enable "$service_name"
    systemctl start "$service_name"
  fi
done

pip install -r /usr/lib/euler-copilot-framework/mcp_center/requiremenets.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

SCRIPT_PATH=$(cd $(dirname $0) && pwd)
echo "当前脚本所在目录: $SCRIPT_PATH"

#源码启动systrace和euler-copilot-tune服务
WORK_PATH="$SCRIPT_PATH/servers"
SYSTRACE_FAILSLOW_SETUP="$WORK_PATH/systrace/failslow"
SYSTRACE_MCP_SETUP="$WORK_PATH/systrace/systrace_mcp"
TUNE_SETUP="$WORK_PATH/euler-copilot-tune"
SYSTEMD_SVC1="systrace-mcpserver"
SYSTEMD_SVC2="tune-mcpserver"
REPO_URL="https://mirrors.huaweicloud.com/repository/pypi/simple/"
REPO_HOST="mirrors.huaweicloud.com"
pkill -f /usr/bin/dnf
yum install python3-devel krb5-devel -y
pkill -f /usr/bin/dnf
yum install sysstat perf gcc -y
systemctl start sysstat
yum install sysbench -y

PYTHON_VERSION=$(python3 -V 2>&1 | awk '{print $2}' | cut -d '.' -f 1,2)
# 提取主版本（如 "3.9" → "3"）和次版本（如 "3.9" → "9"）
PY_MAJOR=$(echo "$PYTHON_VERSION" | cut -d '.' -f 1)
PY_MINOR=$(echo "$PYTHON_VERSION" | cut -d '.' -f 2)

if [ -z "$PY_MAJOR" ] || [ -z "$PY_MINOR" ] || ! [[ "$PY_MAJOR" =~ ^[0-9]+$ ]] || ! [[ "$PY_MINOR" =~ ^[0-9]+$ ]]; then
    echo -e "\033[31m错误：无法识别 Python 版本，当前输出为：$(python3 -V 2>&1)\033[0m"
    exit 1
fi

echo -e "\033[34m当前系统 Python 版本：$PYTHON_VERSION\033[0m"
if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 9 ]; then
    echo -e "\033[32mPython 版本符合要求（3.9），无需执行 pip install mcp\033[0m"
else
    echo -e "\033[33mPython 版本不符合要求（需 3.9，当前为 $PYTHON_VERSION），开始执行 pip install mcp...\033[0m"

    if  pip install mcp  -i https://pypi.tuna.tsinghua.edu.cn/simple; then
        echo -e "\033[32mpip install mcp 执行成功！\033[0m"
    else
        echo -e "\033[31m错误：pip install mcp 执行失败，请检查网络或 pip 环境！\033[0m"
        exit 1
    fi
fi

if [ ! -d "$WORK_PATH" ]; then
    echo -e "\033[31m错误：核心工作目录不存在！\033[0m"
    echo -e "目标目录：$WORK_PATH"
    echo -e "请先确认 euler-copilot-framework 已正确部署，或调整 WORK_PATH 路径后重试。"
    exit 1
fi

pip install "$SYSTRACE_FAILSLOW_SETUP" -i $REPO_URL --trusted-host $REPO_HOST
pip install "$SYSTRACE_MCP_SETUP"  -i $REPO_URL --trusted-host $REPO_HOST
pip install "$TUNE_SETUP"  -i $REPO_URL --trusted-host $REPO_HOST

cp -rf $SYSTRACE_FAILSLOW_SETUP/service/systrace-failslow.service /usr/lib/systemd/system/systrace-failslow.service
cp -rf $SYSTRACE_MCP_SETUP/service/systrace-mcpserver.service /usr/lib/systemd/system/systrace-mcpserver.service
mkdir -p /etc/systrace/config/
cp -rf $SYSTRACE_MCP_SETUP/config/*  /etc/systrace/config/
cp -rf $SYSTRACE_FAILSLOW_SETUP/config/*  /etc/systrace/config/

cp -rf $TUNE_SETUP/service/tune-mcpserver.service /usr/lib/systemd/system/tune-mcpserver.service
mkdir -p /etc/euler-copilot-tune
cp -rf $TUNE_SETUP/config /etc/euler-copilot-tune/
cp -rf $TUNE_SETUP/config/.env.yaml /etc/euler-copilot-tune/config/.env.yaml
cp -rf $TUNE_SETUP/scripts /etc/euler-copilot-tune/
cp -rf $TUNE_SETUP/src/knowledge_base /etc/euler-copilot-tune/


systemctl daemon-reload
systemctl enable --now "$SYSTEMD_SVC1"
systemctl enable --now "$SYSTEMD_SVC2"