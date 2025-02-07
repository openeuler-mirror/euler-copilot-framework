# openEuler Copilot Framework AppCenter 设计文档

## 1. 整体设计

AppCenter 是 openEuler Copilot Framework 的应用中心模块, 主要提供以下功能:

- 应用的 CRUD 操作 (创建、读取、更新、删除)
- 应用收藏管理
- 最近使用应用记录
- 应用搜索与过滤
- 应用发布管理

### 1.1 核心组件

- AppCenter Manager: 应用中心管理器, 提供应用相关的核心业务逻辑
- AppCenter Router: 提供 HTTP API 接口
- MongoDB: 存储应用数据

## 2. 数据结构

### 2.1 App 数据模型

![App 数据模型](./uml/appcenter/DB%20AppPool%20数据模型.png)

### 2.2 User 数据模型

![User 数据模型](./uml/appcenter/DB%20User%20数据模型.png)

## 3. 接口设计

### 3.1 HTTP API

| 路径 | 方法 | 描述 |
|------|------|------|
| `/api/app` | `GET` | 获取应用列表 |
| `/api/app` | `POST` | 创建/更新应用 |
| `/api/app/recent` | `GET` | 获取最近使用应用 |
| `/api/app/{appId}` | `GET` | 获取应用详情 |
| `/api/app/{appId}` | `DELETE` | 删除应用 |
| `/api/app/{appId}` | `POST` | 发布应用 |
| `/api/app/{appId}` | `PUT` | 修改应用收藏状态 |

## 4. 核心流程

### 4.1 创建应用流程

![创建应用流程](./uml/appcenter/API%20创建应用.png)

### 4.2 应用搜索流程

![应用搜索流程](./uml/appcenter/API%20搜索应用.png)

### 4.3 获取最近使用的应用流程

![获取最近使用的应用流程](./uml/appcenter/API%20获取最近使用的应用.png)

### 4.4 获取应用详情流程

![获取应用详情流程](./uml/appcenter/API%20获取应用详情.png)

### 4.5 删除应用流程

![删除应用流程](./uml/appcenter/API%20删除应用.png)

### 4.6 发布应用流程

![发布应用流程](./uml/appcenter/API%20发布应用.png)

### 4.7 更改应用收藏状态流程

![更改应用收藏状态流程](./uml/appcenter/API%20收藏应用.png)

## 5. 主要功能实现

### 5.1 应用搜索与过滤

支持以下搜索类型:

- 全文搜索 (名称、描述、作者)
- 按名称搜索
- 按描述搜索
- 按作者搜索

### 5.2 应用收藏管理

- 支持收藏/取消收藏应用
- 记录用户收藏列表
- 支持获取收藏应用列表

### 5.3 最近使用记录

- 记录应用使用次数和最后使用时间
- 支持获取最近使用应用列表
- 按最后使用时间排序

## 6. 安全性设计

- 接口鉴权: 依赖 `verify_user` 中间件进行用户认证
- CSRF 防护: 使用 `verify_csrf_token` 中间件
- 权限控制: 应用删除、发布等操作需验证用户身份
