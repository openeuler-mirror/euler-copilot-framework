# AI容器栈部署指南

## 准备工作

+ 提前安装 [openEuler Copilot System 命令行（智能 Shell）客户端](../../../使用指南/命令行客户端/命令行助手使用指南.md)

+ 修改 /xxxx/xxxx/values.yaml 文件的 `euler-copilot-tune` 部分，将 `enable` 字段改为 `True`

```yaml
enable: True
```

+ 更新环境

```bash
helm upgrade euler-copilot .
```

+ 检查 Compatibility-AI-Infra 目录下的 openapi.yaml 中 `servers.url` 字段，确保AI容器服务的启动地址被正确设置

+ 获取 `$plugin_dir` 插件文件夹的路径，该变量位于 deploy/chart/euler_copilot/values.yaml 中的 `framework` 模块

+ 如果插件目录不存在，需新建该目录

+ 将该目录下的 Compatibility-AI-Infra 文件夹放到 `$plugin_dir` 中

```bash
cp -r ./Compatibility-AI-Infra $PLUGIN_DIR
```

+ 重建 framework pod，重载插件配置

```bash
kubectl delete pod framework-xxxx -n 命名空间
```
