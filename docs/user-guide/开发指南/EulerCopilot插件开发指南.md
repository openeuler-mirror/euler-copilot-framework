# EulerCopilot插件开发指南

最后更新日期：2024/10/09

## 插件基本目录结构

一个第三方服务接入EulerCopilot时，需要提供的目录及文件如下：

```text
test_plugin    # 插件文件夹，该文件夹的名称即为插件ID；
| -- plugin.json    # 插件的元数据，包含插件的描述、插件的鉴权信息等；
| -- openapi.yaml    # （可选）插件的API定义信息，EulerCopilot可通过其中的API定义进行接口调用；
| -- lib    # （可选）工具文件夹，可以存放用户自定义的Python工具；
| | -- __init__.py    # 标识该文件夹是一个Python模块；
| | -- example_tool.py    # Python代码形式的工具；
| -- flows    # （可选）工作流文件夹；
| | -- example_flow.yaml    # 预定义的工作流；
```

## plugin.json

### 作用描述

`plugin.json`为插件的元数据文件，其作用如下：

- 提供插件的名称与描述。名称和描述供EulerCopilot前端展示，及LLM智能插件选择；
- 提供插件的鉴权方式（可选）。
- 提供插件的预定义问题（可选）。

### 基本格式

```json
{
    "id": "data_analysis",
    "name": "智能数据分析",
    "description": "该插件接受用户文件，返回由外置智能数据分析工具生成的Word文档。",
    "predefined_question": "请帮我将该Excel报表转为Word报告。",
    "automatic_flow": false,
    "auth": {
        "type": "header",
        "args": {
            "Authorization": "sk-1234"
        }
    }
}
```

### 字段说明

- ID：插件的ID，用于在EulerCopilot内唯一标识该插件。
	- 要求：小写英文字母与符号的组合
- name：插件的名字，用于提供给前端进行展示。
	- 要求：任意字符串，长度小于15个字。
- description：插件的描述，用户提供给大模型进行自动插件选择。
	- 要求：精准、完整地描述插件的功能、输入与输出。
- predefined_question：插件的预定义问题，用于在用户无输入时自动填充该问题。（建设中）
- automatic_flow：是否将每个API自动拆分为Flow
- auth：插件的鉴权信息
	- type：插件的鉴权类型。可以为“param”、“header”和“cookie”和“oidc”四种类型。
	- args：实际的鉴权字段（键值对）。


## openapi.yaml

### OpenAPI简介

前身为Swagger标准，是一套基于YAML的、规定HTTP API接口数据传输格式的一种标准，广泛用于前后端分离的Web应用开发中。

开发者可以使用[Swagger Editor](https://editor.swagger.io/)，结合[FastAPI自动文档生成](https://fastapi.tiangolo.com/features/)、[OpenAPI标准](https://swagger.io/specification/)等参考/工具进行文档编写。

EulerCopilot使用的OpenAPI文档与OpenAPI 3.0.0文档标准有少量区别，详情请见下文。

### 基本格式

一个最小的OpenAPI文档文件（openapi.yaml）样例如下：

```yaml
openapi: 3.0.0
info:
  version: 1.0.0
  title: "文档标题"

servers:
  - url: "http://example.com:port/suffix"

paths:
  /url:
    post:
      description: "API的描述信息"
      requestBody:
        description: "API请求体的总描述"
        content:
          application/json:
            schema:
              type: object
              required:
                - data
              properties:
                data:
                  type: string
                  example: "字段的样例值"
                  description: "字段的描述信息"
                  pattern: "[\d].[\d]"
      responses:
        '200':
          description: "API返回体的总描述"
          content:
            application/json:
              schema:
                type: object
                properties:
                  name:
                    type: string
                    example: "字段的样例值"
                    description: "字段的描述信息"
```

上述文档描述了这样一个接口：

```text
curl -X POST http://example.com:port/suffix/url \
-H "Content-Type: application/json" \
-d '{"data": "0.1"}'
```

返回值为：

```text
{"name": "test"}
```

### 字段解析

> 由于YAML有诸多层级，因此此处使用如下方式描述YAML中特定的字段：
> 有YAML文件如下
> ```yaml
> a:
>   b1:
>     c: test1
>   b2: ["test2"]
>```
> 则：`a.b1.c`指值为`test1`的字段；`a.b2[]`指值为`["test2"]`的数组。

#### 全局字段

- `openapi`：OpenAPI标准的版本号，一般为`3.0.0`或`3.1.0`；
- `info`：OpenAPI文档的基本信息
  - `info.title`：OpenAPI文档的标题。该字段并未被使用，但依据OpenAPI标准必须填写。
  - `info.version`：OpenAPI文档的版本。该字段并未被使用，但依据OpenAPI标准必须填写。
- `servers[]`：OpenAPI文档对应的服务器地址。**当前只支持1个服务器的情况，即该数组内只能有1条记录**。
  - `servers[].url`：服务器地址
- `paths`：OpenAPI文档中包含的API
  - `paths.post`：指定API的HTTP请求方式，**当前只支持`get`与`post`两个请求方式**；
  - `paths.post.description`：API的描述信息，**请尽量精准、全面地描述该接口的功能、输入和输出**，将影响大模型的行为；
  - `paths.post.requestBody`：API的请求体信息。
    - `paths.post.requestBody.description`：API的请求体描述，将影响大模型的行为；
    - `paths.post.requestBody.content.application/json`：API的请求体类型，**当前只支持`application/json`、`x-www-form-urlencoded`与`multipart/form-data`**；
    - `paths.post.requestBody.content.application/json.schema`：API的请求体Schema，将影响大模型行为；
  - `paths.post.responses`：API的返回值信息
    - `paths.post.responses."200"`：API的状态码，**当前只支持`"200"`作为默认返回值信息**，其他状态码的文档信息将被忽略并使Flow进入错误处理流程；
    - `paths.post.responses."200".description`：API返回信息的描述，将影响大模型的行为；
    - `paths.post.responses."200".content.application/json`：API的返回值类型
    - `paths.post.responses."200".content.application/json.schema`：API的返回值Schema，将影响大模型的行为；

`requestBody`与`responses`两个字段在编写接口文档时必须存在，否则会导致后端服务异常，或大模型准确率大幅度降低。

#### Schema字段

上述全局字段中，`paths.post.requestBody.content.application/json.schema`与`paths.post.responses."200".content.application/json.schema`均为Schema字段，遵循JSON Schema规范。

JSON Schema的全部规范内容可参照[JSON Schema官方文档](https://json-schema.org/understanding-json-schema/reference)。


##### Schema格式样例

有如下的Schema YAML样例：

```yaml
schema:
  - type: object
    required:
      - id
      - name
    description: 对象描述
    properties:
      id:
        type: integer
        description: 用户ID
        pattern: "2"
      name:
        type: string
        description: 用户名
        pattern: "[a-z0-9]{1,20}"
      gender:
        type: string
        description: 性别设置
        enum:
          - male
          - female
          - others
        example: "male"
      posts:
        type: array
        description: 用户发布过的博客ID
        items:
          type: integer
          description: 单篇博客的ID
          default: 10
```

描述了这样一个JSON数据：

```json
{
  "id": 2,
  "name": "abc123",
  "gender": "female",
  "posts": [
    10, 15, 2, 3
  ]
}
```

##### Schema字段类型与作用

YAML格式的Schema编写，可以参考[OpenAPI文档中的DataType章节](https://swagger.io/docs/specification/data-models/data-types)。

下面是针对部分常见字段的说明：

- `type`：字段的类型。支持的类型有：`null`、`integer`、`number`、`string`、`array`和`object`。
- `description`：字段的描述。**请尽量精准、全面地描述该字段的含义**，将影响大模型的行为。
- `pattern`：（可选，对任意type都有效）字段的正则表达式。字段值将严格按照正则表达式的限制生成。
- `required`：（只对`type`为`object`时有效）object中的必需字段。不在required列表中的字段为可选字段，大模型会视情况进行增减。
- `properties`：（只对`type`为`object`时有效）object中各个字段的类型定义。
- `items`：（只对`type`为`array`时有效）array中元素的类型定义。
- `default`：（可选）字段的默认值。在用户指令中没有提及该字段时，大模型将优先考虑使用默认值。
- `example`：（可选）字段的样例值。大模型将使用样例值作为生成格式、解析用户输入的参照。
- `enum`：（可选，对任意type都有效）字段的枚举值。大模型将从枚举值中选择最符合用户指令的那一个作为生成值。

##### Schema字段的编写限制

由于JSON Schema旨在覆盖所有可能的JSON情况，标准复杂多变，因此当前只支持部分JSON Schema语法。有限支持或不支持的JSON Schema情况如下：

- 数组的`PrefixItems`字段暂不考虑支持。当前情况下，JSON数组无法设置固定元素，只能完全由大模型生成。
- `oneOf`字段不考虑支持，接口接受或返回的数据格式必须一致。目前没有应用场景，将视场景数量考虑是否实现。
- `anyOf`字段仅支持1个schema的情况，不支持“多种数据结构满足其一即可”；
- 混合数组暂不考虑的注意事项与支持。当前情况下，JSON数组内的数据类型必须一致；
- `integer`、`number`类型的`minimum`、`maximum`字段暂未支持，请改用`pattern`字段限制数字位数或固定数字的值。

## flow.yaml

### 作用描述

`flow.yaml`是Agent开发者预先规定的、描述“为了达成某一功能，按序组合多个步骤”的文件，也称为“工作流”。采用YAML格式与自定义的字段，方便开发者直接编写和修改。

在目前的实现中，工作流将按顺序全部执行所有步骤，无法在中间暂停或与用户交互。工作流应尽量短小、原子化，不要包含多个低耦合的任务，也不要与其他工作流产生耦合。

- 正确工作流逻辑示例：

```
工作流功能：查询某一主机的所有CVE列表，并生成特定格式输出
步骤1：调用API接口，获取某一主机的全部CVE ID
步骤2：根据获得的CVE ID和给定的输出格式，生成自然语言结果
```

- 错误工作流逻辑示例：多个低耦合任务

```
工作流功能：根据用户输入，到特定的数据库中查询数据。再根据用户输入，查询输入对应的任务metadata。结合数据库中的数据和任务metadata，生成任务报告。
```

查询数据库内数据、查询任务metadata 和 生成报告 可看做是不同任务，使用不同的流进行处理。

- 错误工作流逻辑示例：工作流耦合

```
工作流功能：需要先调用flow_1获取测试数据才能使用该工作流。该工作流的作用是将flow_1返回值中的data字段提取出来并存储在数据库的test_data表中，...
```

工作流间的先后关系应通过用户问题和自然语言上下文进行实现；不同工作流之间暂时无法进行结构化数据的传递。


### 基本格式

一个`flow.yaml`的基本格式如下：

```yaml
name: example_id
description: 这里是样例描述。
on_error:
  call_type: llm
  params:
    system_prompt: You are a helpful assistant.
    user_prompt: |
      当前工具执行发生错误，原始错误信息为：{data}。请向用户展示错误信息，并给出可能的解决方案。

      背景信息：{context}
steps:
  - name: start
    call_type: api
    params:
      endpoint: GET /api/test
    next: flow_choice
  - name: flow_choice
    call_type: choice
    params:
      instruction: 返回值是否为Markdown报告？
      choices:
        - step: report_gen
          description: 返回值不是Markdown格式
        - step: end
          description: 返回值是Markdown格式
  - name: report_gen
    call_type: llm
    params:
      system_prompt: 你是一个擅长Linux系统性能优化，且能够根据具体情况撰写分析报告的智能助手。
      user_prompt: |-
        用户问题：
        {question}

        工具的输出信息：
        {data}

        上下文信息：
        {context}

        当前时间：
        {time}

        根据上述信息，撰写系统性能分析报告。
    next: end
  - name: end
    call_type: none
next_flow:
  - example_2
  - example_3
```

### 字段解析

#### 全局字段

- `name`：Flow的名称。单个Plugin中，Flow的名称必须唯一，否则会导入失败；
- `description`：Flow的描述信息。**请尽量精准、全面地描述该Flow的功能、输入和输出**，将影响大模型的行为；
- `on_error`：Flow执行失败时的错误处理步骤，**为单一、无命名的Step步骤**。
- `steps[]`：Flow中的步骤定义：
  - 每个步骤（Step），包含单个工具（Call）的类型、必要参数等；
  - 每个步骤都有一个步骤名，“start”和“end”是特殊的步骤名。Flow将以start为入口点开始执行，到end步骤结束。
- `next_flow[]`：由开发者手动指定的推荐Flow，将在Flow完成后以问题改写的方式展示在EulerCopilot前端界面。

#### Step字段

Step是Flow中的单一步骤，作用为：使用特定参数，调用特定Call，得到返回结果。

其中包含的YAML字段如下：

- `name`: Step的名字。注意：`start`和`end`是两个特殊的Step名字，Flow总是从`start`开始执行，至`end`结束执行。
- `call_type`：该Step调用的工具类型。目前提供如下几种预制工具：
  - `api`：调用大模型，访问API接口，获得返回内容
  - `llm`：调用大模型，进行结果处理
  - `choice`：调用大模型，进行判断或选择
  - `sql`：调用大模型，进行数据库查询
  - `render`：调用大模型，将从数据库查询到的数据形成ECharts图表
  - `extract`：从上一个步骤的返回值中提取一个或几个字段，避免其他字段内容干扰后续Step的执行，或直接进行提取之后的数据展示
- `params`：Call需要的参数，将在调用Call时将这些参数提供给Call。各类型Call所需的参数如下：
  - api
    - endpoint：API接口的URI
  - llm
    - system_prompt：大模型系统提示词
    - user_prompt：大模型用户提示词
  - sql：无参数
  - render：无参数
  - choice
    - instruction：交由大模型进行判断的命题
    - choices[]：各个选项
      - description：当大模型认为上述命题满足该描述时，选择该选项
      - step: 大模型选择该选项时，下一步跳转到哪个Step执行
  - extract
    - keys[]: 从原始返回值当中提取哪些key

### 其他限制

受大模型Transformer架构的限制，在调用Call时，存在以下注意事项和要求：

- **工具的输入和输出不要超过最大Token上限的80%**。
  - 预设的系统提示词和上下文将占用一部分Token长度。
  - 当前我们使用的模型默认提供了8K（8192）上下文长度，约12000\~14000字符。可根据该数值的80%（即9600\~11200字符）估算可用的Token上限。
- **整个流程中，调用大模型次数越多，所需时间越长**。每个Flow的Step为了进行步骤串联，均至少需要调用1次大模型。每次调用模型的【理想耗时】约为3秒。可以此数据估算整体的运行时间。
- **模型性能数据参考**：以NVIDIA V100*4 设备为例，解析输入的速度约为1200 tokens/s（即1800\~2000字每秒），计算输出的速度约为50 tokens/s（即70\~90字每秒）。


## Prompt编写简述

上述全部字段中的`description`字段将会被以特定方式嵌入大模型提示词中，进而影响大模型行为。为了使大模型的理解和输出更符合预期效果，请开发者尽量以规范的方式编写Prompt。

### Prompt组成

一个Prompt的样例如下：

```text
你是一名专业的报告撰写员，能够根据给定的背景信息完整、准确、清晰地编写分析报告。
编写报告时使用Markdown格式。不要在文本中加入超链接。不要将整个报告内容放置在代码块中。


今天是8月22日，以下是今天至8月24日的天气预报：

| 日期 | 天气 | 最低温度 | 最高温度 |
-----------------------------------
| 8月22日 | 晴 | 26 | 36 |
| 8月23日 | 雨 | 24 | 32 |
| 8月24日 | 晴 | 28 | 39 |

生成一份针对上述天气预报的分析报告，包括每日天气、温度变化趋势与增减衣物提示。报告格式的样例如下：

# 8月22日至8月24日天气分析报告

## 每日天气

## 气温趋势

## 增减衣物提醒
```

Prompt应具有如下关键部分：

- 系统提示词（Prompt）：是全局重要程度最高的文本段
  - 面具（mask）：给大模型设定角色，不同角色下，大模型的作用和效果可能有所区别。例如：`你是一名专业的报告撰写员，能够根据给定的背景信息完整、准确、清晰地编写分析报告。`
  - 全局要求：给大模型设定全局要求，这些要求的遵从性将比后续的其他要求更高（因为位置更靠前）。**注意：遵从度高不等于一定遵守，大模型的随机化特性可能产生不遵守全局要求的答案。**
    - 输出约定：对输出格式进行约定。但这个约定并不是强制的。例如：`编写报告时使用Markdown格式。不要在文本中加入超链接。不要将整个报告内容放置在代码块中。`
    - 输入约定：对输入的数据格式进行描述与解释。例如：`用户将提供一组JSON数据。其中“name”字段为机器主机名，“id”字段为机器ID。`
- 用户提示词（user prompt）：是包含用户问题、背景信息等的文本段
  - 背景信息（context）：也称上下文，包含了大模型生成答案所需的全部必要信息。例如：（见上方天气数据部分）。
    - **注意：大模型缺少对当前环境和常识的概念，因此在必要情况下需在前面给出概念的定义。**
      - 错误示例（独有概念不给出）：`iSula具有轻量化、安全性高、兼容OCI等特点。`
      - 错误示例（需求环境感知）：`帮我查看昨天晚上的机器整体情况`
      - 正确示例：`iSula是由openEuler社区推出的一款通用容器引擎软件。iSula相比Docker等主流容器引擎，具有轻量化、安全性高、兼容开放容器计划（OCI）指定的容器格式标准。`
    - **注意：背景信息不是越长越好。** 给大模型提供的背景信息越多，背景信息中的细节越容易被忽略。
    - **注意：当背景信息远长于用户问题时，建议将背景信息放置在提示词的最后。**
  - 用户问题（question）：包含了用户实际希望大模型进行的操作，以及附加要求。
    - 指令（instruction）：清晰、明确地给出自己的需求，并提供必要信息。例如：`生成一份针对上述天气预报的分析报告，包括每日天气、温度变化趋势与增减衣物提示。`
      - 错误示例（要求不明确）：`帮我查询openEuler`
      - 错误示例（二义性）：`iSula和Docker哪个更合适？`
      - 错误示例（不相关信息太多）：`你说的对，Linux是很重要的操作系统类型之一。但我还是不太明白Linux和openGauss的关系。能帮我查一下openGauss是否与MySQL兼容吗？`
      - 错误示例（错别字）：`Open eular 和 open gouss 是什么关系？`
    - 附加要求：是重要程度较低的要求。如果希望大模型尽可能严格的按照该要求进行生成，**推荐直接放置在系统提示词中**。

### API接口Description样例

- 功能样例：`调用Stable Diffusion模型，生成图片`
- 描述样例（只保留description字段）：

```yaml
paths:
  /txt2img:
    description: 使用Stable Diffusion模型，生成符合用户要求的图片。
    requestBody:
      ...
        schema:
          properties:
            prompt:
              description: "用于调用Stable Diffusion模型的提示词。必须是英文字符串。使用逗号分隔多个Tag。不同的Tag要描述图片的不同属性，如物体、颜色、特征、风格等。每个Tag长度需小于20个字母。例子：`masterpiece, fantasy, universe, galaxy`"
```

### Flow Description样例

- 功能样例：`查询某一主机的所有CVE列表，并生成特定格式输出。`
- 描述样例：`用于查询**单台**主机的所有CVE，接收主机的ID作为输入信息，并以Markdown列表的形式进行输出。`
