# AI容器栈部署指南

## 准备工作

+  提前部署euler-copilot-shell 客户端

+  修改 /xxxx/xxxx/values.yaml 文件的 euler-copilot-tune 部分，将enable字段改为True

```bash
enable: True
```

+   更新环境

```bash
helm upgrade euler-copilot .
```

+  检查Compatibility-AI-Infra目录下的openapi.yaml 中 servers.url 字段，确保AI容器服务的启动地址被正确设置

+  将该目录下的Compatibility-AI-Infra文件夹放到 $PLUGIN_DIR 中

```bash
cp -r ./Compatibility-AI-Infra $PLUGIN_DIR
```

+ 重建framework pod，重载插件配置
```bash
kubectl delete pod framework-xxxx -n 命名空间
```


