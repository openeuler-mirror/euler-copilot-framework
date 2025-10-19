# Euler Copilot Framework - Authelia 集成指南

本文档介绍如何在 Euler Copilot Framework 中集成和使用 Authelia 作为身份认证和授权服务。

## 概述

Euler Copilot Framework 现在支持两种身份认证方式：
1. **AuthHub** - 传统的内置身份认证服务
2. **Authelia** - 现代化的 OIDC 身份认证服务

## 新增功能

### 1. 代码沙箱服务 (OpenEuler Intelligence Sandbox)

- **位置**: `deploy/chart/euler_copilot/templates/sandbox/`
- **配置**: `deploy/chart/euler_copilot/configs/sandbox/`
- **功能**: 提供安全的代码执行环境，支持 Python、JavaScript、Bash 等语言

### 2. Authelia 身份认证服务

- **位置**: `deploy/chart/authelia/`
- **功能**: 提供 OIDC 兼容的身份认证和授权服务
- **特性**: 
  - 支持多因素认证（可配置）
  - OIDC/OAuth2 兼容
  - 基于文件的用户管理
  - 会话管理

### 3. 灵活的鉴权服务部署

- **脚本**: `deploy/scripts/7-install-auth-service/install_auth_service.sh`
- **功能**: 支持选择部署 AuthHub 或 Authelia

## 部署方式

### 方式一：使用部署脚本选择鉴权服务

```bash
cd /opt/euler-copilot-framework/deploy/scripts
./deploy.sh
# 选择 "7) 安装鉴权服务"，然后选择要部署的服务类型
```

### 方式二：直接使用鉴权服务安装脚本

```bash
# 部署 Authelia
cd /opt/euler-copilot-framework/deploy/scripts/7-install-auth-service
./install_auth_service.sh --service authelia --address http://your-host:30091

# 部署 AuthHub
./install_auth_service.sh --service authhub --address http://your-host:30081
```

### 方式三：使用 Authelia 一键部署脚本

```bash
cd /opt/euler-copilot-framework/deploy/scripts/9-other-script
./deploy_with_authelia.sh --authelia_address http://your-host:30091 --euler_address http://your-host:30080
```

## 配置说明

### Authelia 配置

在 `values.yaml` 中配置 Authelia：

```yaml
# 登录设置
login:
  provider: authelia  # 设置为 authelia
  authelia:
    client_id: euler-copilot
    client_secret: your-client-secret-here

# 域名设置
domain:
  euler_copilot: http://your-host:30080
  authelia: http://your-host:30091
```

### 代码沙箱配置

```yaml
euler_copilot:
  sandbox:
    enabled: true
    security:
      enabled: true
      maxExecutionTime: 30
      maxMemoryMB: 512
    queue:
      maxSize: 100
      workerThreads: 4
```

## 默认账号

### Authelia 默认账号
- **管理员**: `admin` / `admin123`
- **普通用户**: `user` / `user123`

### AuthHub 默认账号
- **管理员**: `administrator` / `changeme`

## 安全注意事项

⚠️ **生产环境重要提示**：

1. **修改默认密码**: 所有默认密码都必须在生产环境中修改
2. **更新密钥**: 修改 Authelia 配置中的所有密钥：
   - `session.secret`
   - `storage.encryption_key`
   - `identity_validation.reset_password.jwt_secret`
   - `identity_providers.oidc.hmac_secret`
3. **生成新的 OIDC 签名密钥**: 替换默认的 RSA 私钥
4. **配置 TLS**: 在生产环境中启用 HTTPS
5. **限制访问**: 配置适当的网络策略和防火墙规则

## 服务端口

| 服务 | 默认端口 | 说明 |
|------|----------|------|
| EulerCopilot Web | 30080 | 主要的 Web 界面 |
| AuthHub | 30081 | AuthHub 认证服务 |
| Authelia | 30091 | Authelia 认证服务 |
| 代码沙箱 | 8000 | 代码执行服务（集群内部） |

## 故障排除

### 1. 检查 Pod 状态
```bash
kubectl get pods -n euler-copilot
kubectl logs -n euler-copilot <pod-name>
```

### 2. 检查服务状态
```bash
kubectl get svc -n euler-copilot
```

### 3. 检查配置
```bash
kubectl get configmap -n euler-copilot
kubectl describe configmap framework-config -n euler-copilot
```

### 4. 常见问题

**问题**: Authelia 登录后重定向失败
**解决**: 检查 `redirect_uris` 配置是否与实际访问地址匹配

**问题**: 代码沙箱服务无法访问
**解决**: 确认 sandbox 服务已启用且 Pod 正常运行

**问题**: 配置文件模板错误
**解决**: 检查 values.yaml 中的配置是否正确，特别是域名和端口设置

## 升级指南

从 AuthHub 迁移到 Authelia：

1. 备份现有配置和数据
2. 更新 `values.yaml` 中的 `login.provider` 为 `authelia`
3. 配置 Authelia 相关参数
4. 重新部署服务
5. 更新用户访问方式

## 技术支持

如有问题，请检查：
1. Kubernetes 集群状态
2. Helm Release 状态
3. 网络连通性
4. 配置文件语法

更多信息请参考：
- [Authelia 官方文档](https://www.authelia.com/)
- [Euler Copilot Framework 文档](../README.md)
