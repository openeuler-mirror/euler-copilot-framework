#!/bin/bash
set -e

# 关键路径（只改这里就行）
VENV_PATH="/usr/lib/sysagent/mcp_center/servers/oe_cli_mcp_server/venv/global"
REQUIREMENTS="/usr/lib/sysagent/mcp_center/servers/oe_cli_mcp_server/requirements.txt"
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"  # 镜像源（保持原有）

# 新增1：安装创建虚拟环境的必需工具（解决隐性创建失败）
yum install -y python3-venv --skip-broken >/dev/null 2>&1

# 新增2：创建虚拟环境父目录（避免二级目录创建失败）
mkdir -p $(dirname "$VENV_PATH") >/dev/null 2>&1

# 1. 没有虚拟环境就创建（新增：--system-site-packages 继承系统 RPM 依赖）
if [ ! -d "$VENV_PATH" ] || [ ! -f "$VENV_PATH/bin/activate" ]; then  # 新增：检查环境完整性
  echo "=== 未找到虚拟环境或环境不完整，创建并继承系统 RPM 依赖 ==="
  rm -rf "$VENV_PATH"  # 删除损坏目录
  python3 -m venv "$VENV_PATH" --system-site-packages
  chmod -R 755 "$VENV_PATH"  # 新增：赋予执行权限
  echo "虚拟环境创建成功：$VENV_PATH"
else
  echo "=== 虚拟环境已存在且完整：$VENV_PATH ==="
fi

# 2. 激活虚拟环境
source "$VENV_PATH/bin/activate"
echo "=== 虚拟环境激活成功：$VIRTUAL_ENV ==="

# 3. 升级 pip（新增：有网才升级，无网跳过）
echo -e "\n=== 升级 pip ==="
if curl -s --connect-timeout 3 "$PIP_MIRROR" >/dev/null 2>&1; then
  pip install --upgrade pip -i "$PIP_MIRROR" --trusted-host pypi.tuna.tsinghua.edu.cn
else
  echo "❌ 无网络连接，跳过 pip 升级"
fi

# 4. 安装依赖（新增：有网才装，且只装系统/RPM 没有的包）
echo -e "\n=== 安装项目依赖 ==="
if [ -f "$REQUIREMENTS" ]; then
  if curl -s --connect-timeout 3 "$PIP_MIRROR" >/dev/null 2>&1; then
    echo "✅ 网络正常，从镜像源安装缺失依赖"

    # 遍历 requirements.txt，只安装系统/RPM 未有的包
    while IFS= read -r pkg; do
      [[ -z "$pkg" || "$pkg" =~ ^# ]] && continue  # 跳过注释、空行

      # 提取包名（忽略版本号）
      pkg_name=$(echo "$pkg" | sed -E 's/[<>=~].*//g' | xargs)

      # 检查包是否已通过系统 RPM 安装（虚拟环境继承）
      if ! python3 -c "import $pkg_name" 2>/dev/null; then
        echo "⚠️  系统未找到 $pkg_name，通过 pip 安装..."
        pip install "$pkg" -i "$PIP_MIRROR" --trusted-host pypi.tuna.tsinghua.edu.cn
      else
        echo "✅ $pkg_name（系统 RPM 已安装，跳过）"
      fi
    done < "$REQUIREMENTS"

  else
    echo "❌ 无网络连接，跳过依赖安装"
    echo "✅ 系统 RPM 依赖已通过虚拟环境继承，可直接使用"
  fi
else
  echo "❌ 未找到依赖文件：$REQUIREMENTS"
fi

echo -e "\n=== 环境配置完成！==="

# 3. 部署systemd服务
cp /usr/lib/sysagent/mcp_center/servers/oe_cli_mcp_server/mcp-server.service /etc/systemd/system/
# 新增：替换服务文件中的 Python 路径（确保与虚拟环境一致）
sed -i "s|ExecStart=.*python|ExecStart=$VENV_PATH/bin/python|" /etc/systemd/system/mcp-server.service
systemctl daemon-reload
systemctl enable mcp-server --now

# 4. 全局命令链接
chmod +x /usr/lib/sysagent/mcp_center/servers/oe_cli_mcp_server/mcp_server/cli.py
rm -f /usr/local/bin/mcp-server
ln -s /usr/lib/sysagent/mcp_center/servers/oe_cli_mcp_server/mcp_server/cli.py /usr/local/bin/mcp-server