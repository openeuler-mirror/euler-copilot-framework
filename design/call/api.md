# API Call 模块设计文档

## 模块概述

API Call 模块是 Scheduler 框架中的核心调用工具，用于向外部 API 接口发送 HTTP 请求并获取数据。该模块支持多种 HTTP 方法、认证方式和内容类型，提供了完整的 API 调用能力。

## 核心组件

### 1. API 类 (api.py)

主要的 API 调用工具类，继承自 `CoreCall`，实现了完整的 API 调用流程。

### 2. Schema 类 (schema.py)

定义了 API 调用的输入输出数据结构：

- `APIInput`: API 调用的输入参数
- `APIOutput`: API 调用的输出结果

## 类结构图

```mermaid
classDiagram
    class API {
        +enable_filling: bool
        +url: str
        +method: HTTPMethod
        +content_type: ContentType
        +timeout: int
        +body: dict
        +query: dict
        -_service_id: str
        -_session_id: str
        -_auth: ServiceApiAuth
        -_client: httpx.AsyncClient
        +info(language) CallInfo
        #_init(call_vars) APIInput
        #_exec(input_data) AsyncGenerator
        -_make_api_call(data, files) httpx.Response
        -_apply_auth() tuple
        -_call_api(final_data) APIOutput
    }

    class APIInput {
        +url: str
        +method: str
        +query: dict
        +body: dict
    }

    class APIOutput {
        +http_code: int
        +result: dict
    }

    API ..> APIInput : uses
    API ..> APIOutput : produces

    note for API "继承自CoreCall基类<br/>详见core.md"
    note for APIInput "继承自DataBase<br/>详见core.md"
    note for APIOutput "继承自DataBase<br/>详见core.md"
```

## 执行流程图

### 主流程

```mermaid
flowchart TD
    Start([开始]) --> Instance[实例化API对象]
    Instance --> Init[_init 初始化]
    Init --> CheckNode{检查Node是否存在}
    CheckNode -->|否| Error1[抛出CallError]
    CheckNode -->|是| CheckService{是否有ServiceId}

    CheckService -->|否| CreateInput[创建APIInput]
    CheckService -->|是| GetMetadata[获取Service Metadata]
    GetMetadata --> GetAuth[获取认证信息]
    GetAuth --> CreateInput

    CreateInput --> SetInput[设置输入数据]
    SetInput --> Exec[_exec 执行]

    Exec --> CreateClient[创建HTTP客户端]
    CreateClient --> ValidateInput[验证输入数据]
    ValidateInput --> CallAPI[调用_call_api]

    CallAPI --> MakeCall[_make_api_call]
    MakeCall --> CheckAuth{是否需要认证}
    CheckAuth -->|是| ApplyAuth[_apply_auth应用认证]
    CheckAuth -->|否| BuildReq[构建请求]
    ApplyAuth --> BuildReq

    BuildReq --> CheckMethod{检查HTTP方法}
    CheckMethod -->|GET/DELETE| BuildGET[构建GET请求]
    CheckMethod -->|POST/PUT/PATCH| BuildPOST[构建POST请求]

    BuildGET --> SendReq[发送HTTP请求]
    BuildPOST --> CheckContentType{检查Content-Type}
    CheckContentType -->|JSON| SetJSON[设置JSON请求体]
    CheckContentType -->|Form| SetForm[设置Form请求体]
    CheckContentType -->|Multipart| SetMultipart[设置Multipart请求体]
    CheckContentType -->|不支持| Error2[抛出CallError]

    SetJSON --> SendReq
    SetForm --> SendReq
    SetMultipart --> SendReq

    SendReq --> CheckStatus{检查HTTP状态码}
    CheckStatus -->|失败| Error3[抛出CallError]
    CheckStatus -->|成功| ParseResp[解析响应]

    ParseResp --> CheckEmpty{响应是否为空}
    CheckEmpty -->|是| ReturnEmpty[返回空结果]
    CheckEmpty -->|否| ParseJSON[解析JSON]

    ParseJSON --> CheckJSON{是否为有效JSON}
    CheckJSON -->|否| Error4[抛出CallError]
    CheckJSON -->|是| CreateOutput[创建APIOutput]

    ReturnEmpty --> YieldChunk[生成输出Chunk]
    CreateOutput --> YieldChunk
    YieldChunk --> CloseClient[关闭HTTP客户端]
    CloseClient --> End([结束])

    Error1 --> End
    Error2 --> End
    Error3 --> End
    Error4 --> End

    style Start fill:#4caf50
    style End fill:#f44336
    style Error1 fill:#ff9800
    style Error2 fill:#ff9800
    style Error3 fill:#ff9800
    style Error4 fill:#ff9800
```

### 认证流程

```mermaid
flowchart TD
    Start([开始认证]) --> CheckSession{检查Session ID}
    CheckSession -->|不存在| Error[抛出CallError]
    CheckSession -->|存在| InitVars[初始化认证变量]

    InitVars --> req_header["req_header = {}"]
    InitVars --> req_cookie["req_cookie = {}"]
    InitVars --> req_params["req_params = {}"]

    req_header --> CheckAuth{检查_auth}
    req_cookie --> CheckAuth
    req_params --> CheckAuth

    CheckAuth -->|不存在| Return[返回空认证信息]
    CheckAuth -->|存在| ProcessAuth[处理认证信息]

    ProcessAuth --> CheckHeader{是否有Header认证}
    CheckHeader -->|是| AddHeader[添加Header项]
    CheckHeader -->|否| CheckCookie{是否有Cookie认证}
    AddHeader --> CheckCookie

    CheckCookie -->|是| AddCookie[添加Cookie项]
    CheckCookie -->|否| CheckQuery{是否有Query认证}
    AddCookie --> CheckQuery

    CheckQuery -->|是| AddQuery[添加Query项]
    CheckQuery -->|否| CheckOIDC{是否有OIDC认证}
    AddQuery --> CheckOIDC

    CheckOIDC -->|是| GetToken[获取Plugin Token]
    CheckOIDC -->|否| Return
    GetToken --> AddToken[添加access-token到Header]
    AddToken --> Return

    Return --> End([返回认证信息])
    Error --> End

    style Start fill:#4caf50
    style End fill:#2196f3
    style Error fill:#ff9800
```

## 时序图

### 完整调用时序

```mermaid
sequenceDiagram
    participant Executor as StepExecutor
    participant API as API实例
    participant Client as HTTP Client
    participant Service as ServiceCenter
    participant Token as TokenManager
    participant ExtAPI as 外部API

    Executor->>+API: instance(executor, node)
    API->>API: __init__(参数)
    API->>+API: _set_input(executor)
    API->>+API: _init(call_vars)

    alt 存在ServiceId
        API->>+Service: get_service_metadata(user_id, service_id)
        Service-->>-API: service_metadata
        API->>API: 保存_auth认证信息
    end

    API->>API: 创建APIInput对象
    API-->>-API: 返回APIInput
    API->>API: 保存input数据
    API-->>-API: 完成初始化
    API-->>-Executor: 返回API实例

    Executor->>+API: exec(executor, input_data)
    API->>+API: _exec(input_data)
    API->>+Client: 创建AsyncClient
    Client-->>-API: client实例

    API->>API: 验证input_data
    API->>+API: _call_api(input_obj)
    API->>+API: _make_api_call(data, files)

    alt 需要认证
        API->>+API: _apply_auth()

        alt 存在OIDC认证
            API->>+Token: get_plugin_token(...)
            Token-->>-API: access_token
            API->>API: 添加token到header
        end

        API->>API: 组装header/cookie/params
        API-->>-API: 返回认证信息
    end

    API->>API: 创建request_factory

    alt GET/DELETE请求
        API->>API: 合并query参数
        API->>+Client: request(method, url, params)
    else POST/PUT/PATCH请求
        API->>API: 根据Content-Type处理body
        API->>+Client: request(method, url, json/data/files)
    end

    Client->>+ExtAPI: 发送HTTP请求
    ExtAPI-->>-Client: HTTP响应
    Client-->>-API: response对象
    API-->>-API: 返回response

    alt 状态码异常
        API->>API: 抛出CallError
    else 状态码正常
        API->>API: 解析response.text

        alt 响应为空
            API->>API: 返回空APIOutput
        else 响应非空
            API->>API: 解析JSON
            alt JSON解析失败
                API->>API: 抛出CallError
            else JSON解析成功
                API->>API: 创建APIOutput
            end
        end
    end

    API-->>-API: 返回APIOutput
    API->>API: 创建CallOutputChunk
    API->>Executor: yield chunk

    API->>+Client: aclose()
    Client-->>-API: 关闭完成

    API-->>-API: 完成执行
    API-->>-Executor: 执行完成
```

### 认证处理时序

```mermaid
sequenceDiagram
    participant API as API实例
    participant Auth as _apply_auth
    participant Token as TokenManager
    participant OIDC as OIDC Provider

    API->>+Auth: 调用认证
    Auth->>Auth: 检查session_id

    alt session_id不存在
        Auth->>Auth: 抛出CallError
        Auth-->>API: 错误
    else session_id存在
        Auth->>Auth: 初始化req_header/cookie/params

        alt _auth存在
            loop 遍历header列表
                Auth->>Auth: 添加header项
            end

            loop 遍历cookie列表
                Auth->>Auth: 添加cookie项
            end

            loop 遍历query列表
                Auth->>Auth: 添加params项
            end

            alt 存在OIDC配置
                Auth->>+OIDC: get_access_token_url()
                OIDC-->>-Auth: token_url

                Auth->>+Token: get_plugin_token(service_id, session_id, token_url, 30)
                Token-->>-Auth: access_token

                Auth->>Auth: 添加access-token到header
            end
        end

        Auth-->>-API: 返回(req_header, req_cookie, req_params)
    end
```

## 状态图

### API调用状态流转

```mermaid
stateDiagram-v2
    [*] --> 未初始化

    未初始化 --> 初始化中: instance()
    初始化中 --> 初始化失败: Node不存在
    初始化中 --> 初始化失败: Service获取失败
    初始化中 --> 已初始化: 初始化成功

    已初始化 --> 执行中: exec()
    执行中 --> 创建客户端: 创建AsyncClient
    创建客户端 --> 准备请求: 验证输入

    准备请求 --> 应用认证: 需要认证
    准备请求 --> 构建请求: 无需认证
    应用认证 --> 认证失败: Session不存在
    应用认证 --> 构建请求: 认证成功

    构建请求 --> 构建失败: Content-Type不支持
    构建请求 --> 构建失败: HTTP Method不支持
    构建请求 --> 发送请求: 构建成功

    发送请求 --> 请求失败: HTTP错误
    发送请求 --> 解析响应: HTTP成功

    解析响应 --> 解析失败: JSON解析失败
    解析响应 --> 生成输出: 解析成功
    解析响应 --> 生成输出: 响应为空

    生成输出 --> 清理资源: yield chunk
    清理资源 --> 执行完成: 关闭客户端

    初始化失败 --> [*]
    认证失败 --> [*]
    构建失败 --> [*]
    请求失败 --> [*]
    解析失败 --> [*]
    执行完成 --> [*]
```

## 关键特性

### 1. HTTP 方法支持

支持的 HTTP 方法：

- GET
- POST
- PUT
- PATCH
- DELETE

```mermaid
graph LR
    A[HTTP Method] --> B[GET]
    A --> C[POST]
    A --> D[PUT]
    A --> E[PATCH]
    A --> F[DELETE]

    B --> G[参数传递: Query Params]
    C --> H[参数传递: Body]
    D --> H
    E --> H
    F --> G

    style A fill:#2196f3,color:#fff
    style B fill:#4caf50
    style C fill:#4caf50
    style D fill:#4caf50
    style E fill:#4caf50
    style F fill:#4caf50
```

### 2. Content-Type 支持

```mermaid
graph TB
    ContentType[Content-Type支持]
    ContentType --> JSON[application/json<br/>JSON格式数据]
    ContentType --> Form[application/x-www-form-urlencoded<br/>表单数据]
    ContentType --> Multipart[multipart/form-data<br/>文件上传]

    JSON --> JSONHandler[json参数]
    Form --> FormHandler[data参数]
    Multipart --> MultipartHandler[data参数（files参数尚未接入输入模型）]

    style ContentType fill:#673ab7,color:#fff
    style JSON fill:#9c27b0,color:#fff
    style Form fill:#9c27b0,color:#fff
    style Multipart fill:#9c27b0,color:#fff
```

### 3. 认证方式

```mermaid
graph TB
    AuthTypes[认证方式]
    AuthTypes --> Header[Header认证<br/>请求头携带认证信息]
    AuthTypes --> Cookie[Cookie认证<br/>Cookie携带认证信息]
    AuthTypes --> Query[Query认证<br/>URL参数携带认证信息]
    AuthTypes --> OIDC[OIDC认证<br/>OpenID Connect令牌]

    Header --> HeaderExample[例: Authorization: Bearer token]
    Cookie --> CookieExample[例: session_id=xyz123]
    Query --> QueryExample[例: ?api_key=abc123]
    OIDC --> OIDCExample[例: access-token: eyJhbGc...]

    style AuthTypes fill:#ff5722,color:#fff
    style Header fill:#ff7043
    style Cookie fill:#ff7043
    style Query fill:#ff7043
    style OIDC fill:#ff7043
```

### 4. 成功状态码

模块识别的成功 HTTP 状态码范围：

```mermaid
graph LR
    Success[成功状态码]

    Success --> S2xx[2xx 成功响应]
    Success --> S3xx[3xx 重定向]

    S2xx --> S200[200 OK]
    S2xx --> S201[201 Created]
    S2xx --> S202[202 Accepted]
    S2xx --> S204[204 No Content]
    S2xx --> S203[203 Non-Authoritative Information]
    S2xx --> S205[205 Reset Content]
    S2xx --> S206[206 Partial Content]
    S2xx --> S207[207 Multi-Status]
    S2xx --> S208[208 Already Reported]
    S2xx --> S226[226 IM Used]

    S3xx --> S301[301 Moved Permanently]
    S3xx --> S302[302 Found]
    S3xx --> S303[303 See Other]
    S3xx --> S304[304 Not Modified]
    S3xx --> S307[307 Temporary Redirect]
    S3xx --> S308[308 Permanent Redirect]

    style Success fill:#4caf50,color:#fff
    style S2xx fill:#66bb6a
    style S3xx fill:#66bb6a
```

## 错误处理

### 错误场景

```mermaid
graph TB
    Errors[错误场景]

    Errors --> E1[Node未指定]
    Errors --> E2[Service Metadata获取失败]
    Errors --> E3[Content-Type未指定]
    Errors --> E4[Content-Type不支持]
    Errors --> E5[HTTP Method不支持]
    Errors --> E6[Session ID未设置]
    Errors --> E7[HTTP状态码异常]
    Errors --> E8[返回值非JSON格式]

    E1 --> Action1[抛出CallError]
    E2 --> Action2[抛出CallError]
    E3 --> Action3[抛出CallError]
    E4 --> Action4[抛出CallError]
    E5 --> Action5[抛出CallError]
    E6 --> Action6[抛出CallError]
    E7 --> Action7[抛出CallError<br/>附带状态码和原因]
    E8 --> Action8[抛出CallError]

    style Errors fill:#f44336,color:#fff
    style E1 fill:#ef5350
    style E2 fill:#ef5350
    style E3 fill:#ef5350
    style E4 fill:#ef5350
    style E5 fill:#ef5350
    style E6 fill:#ef5350
    style E7 fill:#ef5350
    style E8 fill:#ef5350
```

## 配置参数

### API 类配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | str | 必填 | API接口的完整URL |
| `method` | HTTPMethod | 必填 | HTTP方法 |
| `content_type` | ContentType | None | Content-Type |
| `timeout` | int | 300 | 超时时间（秒），必须大于30 |
| `body` | dict | {} | 已知的部分请求体 |
| `query` | dict | {} | 已知的部分请求参数 |
| `enable_filling` | bool | True | 是否需要自动参数填充 |
| `to_user` | bool | False | 是否将输出返回给用户 |

## 实现注意事项

- 认证信息虽然会在 `_apply_auth` 中生成 Header/Cookie/Query 三类数据，但当前实现仅将 Cookie 和 Query 透传至 `httpx` 请求，Header 信息尚未写入请求参数，依赖 Header 的认证策略暂时无效。
- `files` 参数作为占位符传入 `_make_api_call`，但 `APIInput` 尚未提供文件字段，Multipart 上传只能提交表单字段，文件内容暂未接入。
- 当外部返回的响应体不是合法 JSON 时会抛出 `CallError`，不会返回原始字符串结果。

### 配置关系图

```mermaid
graph TB
    Config[API配置]

    Config --> Required[必填参数]
    Config --> Optional[可选参数]

    Required --> url[url: 接口地址]
    Required --> method[method: HTTP方法]

    Optional --> content_type[content_type: 内容类型]
    Optional --> timeout[timeout: 超时时间]
    Optional --> body[body: 请求体]
    Optional --> query[query: 查询参数]
    Optional --> enable_filling[enable_filling: 自动填充]
    Optional --> to_user[to_user: 返回用户]

    style Config fill:#00bcd4,color:#fff
    style Required fill:#0097a7,color:#fff
    style Optional fill:#00acc1,color:#fff
```

## 生命周期

```mermaid
sequenceDiagram
    participant M as 模块加载
    participant I as 实例创建
    participant Init as 初始化
    participant Exec as 执行
    participant Clean as 清理

    M->>M: 导入API类
    M->>M: 注册input_model/output_model

    I->>I: API.instance()
    I->>Init: _set_input()
    Init->>Init: _init()
    Init->>Init: 获取Service Metadata
    Init->>Init: 设置认证信息
    Init->>I: 返回APIInput
    I->>I: 保存input数据

    Exec->>Exec: exec()
    Exec->>Exec: _exec()
    Exec->>Exec: 创建HTTP客户端
    Exec->>Exec: 调用API
    Exec->>Exec: 处理响应
    Exec->>Exec: 生成输出

    Exec->>Clean: 执行完成
    Clean->>Clean: 关闭HTTP客户端
    Clean->>Clean: 释放资源
```
