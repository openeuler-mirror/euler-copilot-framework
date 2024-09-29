# AuthHub 部署指南

## 准备工作

+   将 values.yaml 中的 authHub-web，authHub 的 enable 字段改为True

```bash
enable: True
```

+   更新环境

```bash
helm upgrade service .
```

