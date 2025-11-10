# Provider配置更新总结

## 更新时间
2025年11月10日

## 更新内容

### 1. 新增在线服务平台配置（已完成）

#### Spark（讯飞星火）
- **API地址**: `https://spark-api-open.xf-yun.com/v1`
- **认证方式**: Bearer Token
- **能力特点**:
  - ✅ 支持流式输出、函数调用、JSON模式
  - ✅ 支持 top_k 参数
  - ✅ 不支持 thinking/reasoning
- **配置模型**:
  - `spark:generalv3.5` - 星火 V3.5
  - `spark:generalv3` - 星火 V3.0
  - `spark:4.0Ultra` - 星火 4.0 Ultra
  - `spark:embedding-2.5` - 星火文本嵌入 2.5

#### Wenxin（百度文心）
- **API地址**: `https://qianfan.baidubce.com/v2`
- **认证方式**: Bearer Token
- **能力特点**:
  - ✅ 支持流式输出、函数调用、JSON模式
  - ✅ 支持 frequency_penalty 和 presence_penalty
  - ✅ 支持联网搜索（enable_search）
  - ✅ 不支持 top_k
- **配置模型**:
  - `wenxin:ernie-4.0-turbo-8k` - 文心一言 4.0 Turbo
  - `wenxin:ernie-4.0-8k` - 文心一言 4.0
  - `wenxin:ernie-3.5-128k` - 文心一言 3.5 128K
  - `wenxin:ernie-speed-128k` - 文心一言 Speed
  - `wenxin:ernie-lite-8k` - 文心一言 Lite
  - `wenxin:embedding-v1` - 文心向量 V1

### 2. 新增本地部署框架配置（已完成）

#### Ollama
- **默认API地址**: `http://localhost:11434/v1`
- **认证方式**: 无需认证（none）
- **能力特点**:
  - ✅ 完整的OpenAI兼容API
  - ✅ 支持流式、函数调用、JSON模式
  - ✅ 支持 top_k、frequency_penalty、presence_penalty
  - ⚠️ API地址可由用户自定义
- **参考文档**: https://ollama.com/docs/api

#### vLLM
- **默认API地址**: `http://localhost:8000/v1`
- **认证方式**: 无需认证（none）
- **能力特点**:
  - ✅ 高性能OpenAI兼容API
  - ✅ 支持流式、函数调用、JSON模式
  - ✅ 支持 top_k、frequency_penalty、presence_penalty
  - ✅ 支持 extra_body 扩展参数
  - ⚠️ API地址可由用户自定义
- **参考文档**: https://vllm.readthedocs.io/

#### MindIE（华为昇腾）
- **默认API地址**: `http://localhost:8080/v1`
- **认证方式**: 无需认证（none）
- **能力特点**:
  - ✅ 华为昇腾硬件优化
  - ✅ OpenAI兼容API
  - ✅ 支持流式、函数调用、JSON模式
  - ✅ 支持 top_k、extra_body
  - ⚠️ API地址可由用户自定义
- **参考文档**: https://www.hiascend.com/document/detail/zh/canncommercial/60RC1alpha002/developer/mindie/mindie_01_0001.html

#### ModelScope（魔塔）
- **默认API地址**: `http://localhost:8000/v1`
- **认证方式**: 无需认证（none）
- **能力特点**:
  - ✅ 阿里巴巴模型平台
  - ✅ OpenAI兼容API
  - ✅ 支持流式、函数调用、JSON模式
  - ✅ 支持 top_k、frequency_penalty、extra_body
  - ⚠️ API地址可由用户自定义
- **参考文档**: https://modelscope.cn/docs

## 配置文件位置

- **供应商配置**: `/opt/euler-copilot-framework/deploy/chart/euler_copilot/configs/framework/providers.conf`
- **模型配置**: `/opt/euler-copilot-framework/deploy/chart/euler_copilot/configs/framework/models.conf`

## 完整的Provider清单

### 在线服务（Public）
1. ✅ OpenAI
2. ✅ SiliconFlow（硅基流动）
3. ✅ Bailian（阿里百炼）
4. ✅ Baichuan（百川智能）
5. ✅ **Spark（讯飞星火）** - 新增
6. ✅ **Wenxin（百度文心）** - 新增

### 本地部署（Private）
1. ✅ **Ollama** - 新增完整配置
2. ✅ **vLLM** - 新增完整配置
3. ✅ **MindIE** - 新增完整配置
4. ✅ **ModelScope** - 新增完整配置

## 技术说明

### 认证类型说明
- **bearer**: Bearer Token认证，需要在Authorization头中提供token
- **none**: 无需认证，适用于本地部署的服务

### API地址说明
- 在线服务：API地址固定，直接使用配置文件中的地址
- 本地部署：API地址为默认值，用户需要根据实际部署情况修改

### 能力继承机制
- 模型配置通过 `_inherit` 字段继承供应商的默认能力
- 模型可以覆盖供应商的部分能力配置
- 例如：`"_inherit": "spark.chat_capabilities"` 继承spark的chat能力

## 使用建议

### 本地部署框架使用步骤
1. 部署本地推理服务（如Ollama、vLLM等）
2. 在配置中修改对应provider的`api_base_url`为实际地址
3. 在前端配置LLM时，选择对应的provider
4. 填写模型名称（需与本地部署的模型名称一致）

### 配置验证
```bash
# 验证providers.conf格式
python3 -m json.tool deploy/chart/euler_copilot/configs/framework/providers.conf

# 验证models.conf格式
python3 -m json.tool deploy/chart/euler_copilot/configs/framework/models.conf
```

## 已验证状态
- ✅ providers.conf JSON格式正确
- ✅ models.conf JSON格式正确
- ✅ 所有provider已在llm_provider_dict中注册
- ✅ 所有provider已在AdapterFactoryV2中注册

## 下一步建议
1. 添加具体的本地模型配置到models.conf（如ollama支持的具体模型）
2. 完善本地部署框架的文档和使用示例
3. 测试各provider的实际调用情况
