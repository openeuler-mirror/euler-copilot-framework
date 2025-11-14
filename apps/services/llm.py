# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging


from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.schemas.config import EmbeddingConfig, RerankerConfig, LLMConfig, FunctionCallConfig
from apps.schemas.collection import LLM, LLMItem
from apps.schemas.request_data import (
    UpdateLLMReq,
)
from apps.schemas.response_data import LLMProvider, LLMProviderInfo
from apps.templates.generate_llm_operator_config import llm_provider_dict
from apps.llm.schema import DefaultModelId
from apps.llm.model_registry import model_registry
from apps.llm.adapters import get_provider_from_endpoint

logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""

    @staticmethod
    def _create_llm_provider_info(llm: dict) -> LLMProviderInfo:
        """
        从数据库 LLM 文档创建 LLMProviderInfo 对象的辅助方法

        :param llm: 数据库中的 LLM 文档
        :return: LLMProviderInfo 对象
        """
        # 标准化type字段为列表格式
        llm_type = llm.get("type", "chat")
        if isinstance(llm_type, str):
            llm_type = [llm_type]

        return LLMProviderInfo(
            llmId=llm["_id"],  # _id已经是UUID字符串
            icon=llm["icon"],
            openaiBaseUrl=llm["openai_base_url"],
            openaiApiKey=llm["openai_api_key"],
            modelName=llm["model_name"],
            maxTokens=llm["max_tokens"],
            isEditable=bool(llm.get("user_sub")),  # 系统模型（user_sub=""）不可编辑
            type=llm_type,  # 始终返回列表格式

            # 模型能力字段 - 基础能力
            provider=llm.get("provider", ""),
            supportsStreaming=llm.get("supports_streaming", True),
            supportsFunctionCalling=llm.get("supports_function_calling", True),
            supportsJsonMode=llm.get("supports_json_mode", True),
            supportsStructuredOutput=llm.get(
                "supports_structured_output", False),

            # 推理能力
            supportsThinking=llm.get("supports_thinking", False),
            canToggleThinking=llm.get("can_toggle_thinking", False),
            supportsReasoningContent=llm.get(
                "supports_reasoning_content", False),

            # 参数支持
            maxTokensParam=llm.get("max_tokens_param", "max_tokens"),
            supportsTemperature=llm.get("supports_temperature", True),
            supportsTopP=llm.get("supports_top_p", True),
            supportsTopK=llm.get("supports_top_k", False),
            supportsFrequencyPenalty=llm.get(
                "supports_frequency_penalty", False),
            supportsPresencePenalty=llm.get(
                "supports_presence_penalty", False),
            supportsMinP=llm.get("supports_min_p", False),

            # 高级功能
            supportsResponseFormat=llm.get("supports_response_format", True),
            supportsTools=llm.get("supports_tools", True),
            supportsToolChoice=llm.get("supports_tool_choice", True),
            supportsExtraBody=llm.get("supports_extra_body", True),
            supportsStreamOptions=llm.get("supports_stream_options", True),

            # 特殊参数
            supportsEnableThinking=llm.get("supports_enable_thinking", False),
            supportsThinkingBudget=llm.get("supports_thinking_budget", False),
            supportsEnableSearch=llm.get("supports_enable_search", False),

            # 其他信息
            notes=llm.get("notes", ""),
        )

    @staticmethod
    async def list_llm_provider() -> list[LLMProvider]:
        """
        获取大模型提供商列表

        :return: 大模型提供商列表
        """
        provider_list = []
        for provider in llm_provider_dict.values():
            item = LLMProvider(
                provider=provider["provider"],
                url=provider["url"],
                description=provider["description"],
                icon=provider["icon"],
                alias_zh=provider.get("alias_zh", ""),
                alias_en=provider.get("alias_en", ""),
                type=provider.get("type", "public"),
            )
            provider_list.append(item)
        return provider_list

    @staticmethod
    async def get_llm_id_by_conversation_id(user_sub: str, conversation_id: str) -> str:
        """
        通过对话ID获取大模型ID

        :param user_sub: 用户ID
        :param conversation_id: 对话ID
        :return: 大模型ID
        """
        conv_collection = MongoDB.get_collection("conversation")
        result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not result:
            return ""
        return result.get("llm", {}).get("llm_id", "")

    @staticmethod
    async def get_llm_by_id(llm_id: str) -> LLM:
        """
        通过ID获取大模型

        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        llm_collection = MongoDB.get_collection("llm")

        result = await llm_collection.find_one({"_id": llm_id})

        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)

        return LLM.model_validate(result)

    @staticmethod
    async def get_llm_by_user_sub_and_id(user_sub: str, llm_id: str) -> LLM:
        """
        通过ID获取大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        llm_collection = MongoDB.get_collection("llm")

        result = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})

        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)

        return LLM.model_validate(result)

    @staticmethod
    async def list_llm(user_sub: str, llm_id: str | None, model_type: str | None = None) -> list[LLMProviderInfo]:
        """
        获取大模型列表

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :param model_type: 模型类型，可选值：'chat', 'image', 'video', 'speech', 'embedding', 'reranker', 'function_call'
        :return: 大模型列表
        """
        llm_collection = MongoDB.get_collection("llm")

        # 构建查询条件：包含用户模型和系统模型
        base_query = {"$or": [{"user_sub": user_sub}, {"user_sub": ""}]}
        if llm_id:
            base_query["llm_id"] = llm_id
        if model_type:
            # 支持type字段既可以是字符串也可以是数组
            base_query["type"] = model_type

        result = await llm_collection.find(base_query).sort({"created_at": 1}).to_list(length=None)

        llm_list = []
        for llm in result:
            llm_item = LLMManager._create_llm_provider_info(llm)
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def update_llm(user_sub: str, llm_id: str | None, req: UpdateLLMReq) -> str:
        """
        创建或更新大模型，自动推断模型能力

        :param user_sub: 用户ID
        :param llm_id: 大模型ID，为None时创建新模型
        :param req: 创建大模型请求体
        :return: 大模型ID
        """
        llm_collection = MongoDB.get_collection("llm")

        # 推断模型能力
        provider = req.provider or get_provider_from_endpoint(
            req.openai_base_url)

        # 检查provider类型，如果是public类型，则验证URL
        if provider in llm_provider_dict:
            provider_info = llm_provider_dict[provider]
            provider_type = provider_info.get("type", "public")

            # 如果是public类型的provider
            if provider_type == "public":
                standard_url = provider_info.get("url", "")
                # 如果用户提供的URL不为空，且与标准URL不一致
                if req.openai_base_url and req.openai_base_url.rstrip('/') != standard_url.rstrip('/'):
                    err = f"[LLMManager] public类型的provider '{provider}' 不允许自定义URL，应使用标准URL: {standard_url}"
                    logger.error(err)
                    raise ValueError(err)
                # 如果用户没有提供URL，使用标准URL
                if not req.openai_base_url:
                    req.openai_base_url = standard_url

        # 标准化type字段为列表格式
        model_type = req.type
        if isinstance(model_type, str):
            model_type = [model_type]

        # 从model_registry获取完整的模型能力
        from apps.llm.model_types import ModelType
        capabilities_obj = model_registry.get_model_capabilities(
            provider, req.model_name, ModelType.CHAT)

        # 使用请求中的能力信息，如果没有则从capabilities_obj获取，最后使用默认值
        capabilities = {
            "provider": provider,

            # 基础能力
            "supports_streaming": req.supports_streaming if hasattr(req, 'supports_streaming') and req.supports_streaming is not None else (capabilities_obj.supports_streaming if capabilities_obj else True),
            "supports_function_calling": req.supports_function_calling if req.supports_function_calling is not None else (capabilities_obj.supports_function_calling if capabilities_obj else True),
            "supports_json_mode": req.supports_json_mode if req.supports_json_mode is not None else (capabilities_obj.supports_json_mode if capabilities_obj else True),
            "supports_structured_output": req.supports_structured_output if req.supports_structured_output is not None else (capabilities_obj.supports_structured_output if capabilities_obj else False),

            # 推理能力
            "supports_thinking": req.supports_thinking if req.supports_thinking is not None else (capabilities_obj.supports_thinking if capabilities_obj else False),
            "can_toggle_thinking": req.can_toggle_thinking if req.can_toggle_thinking is not None else (capabilities_obj.can_toggle_thinking if capabilities_obj else False),
            "supports_reasoning_content": req.supports_reasoning_content if hasattr(req, 'supports_reasoning_content') and req.supports_reasoning_content is not None else (capabilities_obj.supports_reasoning_content if capabilities_obj else False),

            # 参数支持
            "max_tokens_param": req.max_tokens_param or (capabilities_obj.max_tokens_param if capabilities_obj else "max_tokens"),
            "supports_temperature": req.supports_temperature if hasattr(req, 'supports_temperature') and req.supports_temperature is not None else (capabilities_obj.supports_temperature if capabilities_obj else True),
            "supports_top_p": req.supports_top_p if hasattr(req, 'supports_top_p') and req.supports_top_p is not None else (capabilities_obj.supports_top_p if capabilities_obj else True),
            "supports_top_k": req.supports_top_k if hasattr(req, 'supports_top_k') and req.supports_top_k is not None else (capabilities_obj.supports_top_k if capabilities_obj else False),
            "supports_frequency_penalty": req.supports_frequency_penalty if hasattr(req, 'supports_frequency_penalty') and req.supports_frequency_penalty is not None else (capabilities_obj.supports_frequency_penalty if capabilities_obj else False),
            "supports_presence_penalty": req.supports_presence_penalty if hasattr(req, 'supports_presence_penalty') and req.supports_presence_penalty is not None else (capabilities_obj.supports_presence_penalty if capabilities_obj else False),
            "supports_min_p": req.supports_min_p if hasattr(req, 'supports_min_p') and req.supports_min_p is not None else (capabilities_obj.supports_min_p if capabilities_obj else False),

            # 高级功能
            "supports_response_format": req.supports_response_format if hasattr(req, 'supports_response_format') and req.supports_response_format is not None else (capabilities_obj.supports_response_format if capabilities_obj else True),
            "supports_tools": req.supports_tools if hasattr(req, 'supports_tools') and req.supports_tools is not None else (capabilities_obj.supports_tools if capabilities_obj else True),
            "supports_tool_choice": req.supports_tool_choice if hasattr(req, 'supports_tool_choice') and req.supports_tool_choice is not None else (capabilities_obj.supports_tool_choice if capabilities_obj else True),
            "supports_extra_body": req.supports_extra_body if hasattr(req, 'supports_extra_body') and req.supports_extra_body is not None else (capabilities_obj.supports_extra_body if capabilities_obj else True),
            "supports_stream_options": req.supports_stream_options if hasattr(req, 'supports_stream_options') and req.supports_stream_options is not None else (capabilities_obj.supports_stream_options if capabilities_obj else True),

            # 特殊参数
            "supports_enable_thinking": req.supports_enable_thinking if hasattr(req, 'supports_enable_thinking') and req.supports_enable_thinking is not None else (capabilities_obj.supports_enable_thinking if capabilities_obj else False),
            "supports_thinking_budget": req.supports_thinking_budget if hasattr(req, 'supports_thinking_budget') and req.supports_thinking_budget is not None else (capabilities_obj.supports_thinking_budget if capabilities_obj else False),
            "supports_enable_search": req.supports_enable_search if hasattr(req, 'supports_enable_search') and req.supports_enable_search is not None else (capabilities_obj.supports_enable_search if capabilities_obj else False),

            # 其他信息
            "notes": req.notes or (capabilities_obj.notes if capabilities_obj and hasattr(capabilities_obj, 'notes') else ""),
        }

        if llm_id:
            llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not llm_dict:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise ValueError(err)

            # 检查是否为系统级别模型（不允许编辑）
            if not llm_dict.get("user_sub"):
                err = f"[LLMManager] 系统级别模型 {llm_id} 不允许编辑"
                logger.error(err)
                raise ValueError(err)

            llm = LLM(
                _id=llm_id,
                user_sub=user_sub,
                icon=req.icon if req.icon else llm_dict["icon"],
                openai_base_url=req.openai_base_url,
                openai_api_key=req.openai_api_key,
                model_name=req.model_name,
                max_tokens=req.max_tokens,
                type=model_type,  # 使用标准化后的列表格式
                **capabilities
            )
            # 排除_id字段以避免MongoDB的不可变_id字段错误
            update_data = llm.model_dump(by_alias=True, exclude={"_id"})
            await llm_collection.update_one({"_id": llm_id}, {"$set": update_data})
        else:
            llm = LLM(
                user_sub=user_sub,
                icon=req.icon,
                openai_base_url=req.openai_base_url,
                openai_api_key=req.openai_api_key,
                model_name=req.model_name,
                max_tokens=req.max_tokens,
                type=model_type,  # 使用标准化后的列表格式
                **capabilities
            )
            # 排除_id字段让MongoDB自动生成_id，避免冲突
            insert_data = llm.model_dump(by_alias=True, exclude={"_id"})
            await llm_collection.insert_one(insert_data)
        return llm.id

    @staticmethod
    async def delete_llm(user_sub: str, llm_id: str) -> str:
        """
        删除大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型ID
        """
        if not llm_id:
            err = "[LLMManager] 不能删除系统默认大模型"
            logger.error(err)
            raise ValueError(err)

        llm_collection = MongoDB.get_collection("llm")
        conv_collection = MongoDB.get_collection("conversation")

        llm_config = await llm_collection.find_one({"_id": llm_id})
        if not llm_config:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)

        # 检查是否为系统级别模型（不允许删除）
        if not llm_config.get("user_sub"):
            err = f"[LLMManager] 系统级别模型 {llm_id} 不允许删除"
            logger.error(err)
            raise ValueError(err)

        # 检查是否为当前用户的模型
        if llm_config.get("user_sub") != user_sub:
            err = f"[LLMManager] 无权限删除模型 {llm_id}"
            logger.error(err)
            raise ValueError(err)

        conv_dict = await conv_collection.find_one({"llm.llm_id": llm_id, "user_sub": user_sub})
        if conv_dict:
            # 获取系统默认模型信息
            config = Config().get_config()
            system_llm = await llm_collection.find_one({
                "user_sub": "",
                "type": "chat",
                "model_name": config.llm.model
            })

            await conv_collection.update_many(
                {"_id": conv_dict["_id"], "user_sub": user_sub},
                {"$set": {"llm": {
                    "llm_id": str(system_llm["_id"]),
                    "icon": system_llm["icon"],
                    "model_name": system_llm["model_name"],
                }}},
            )

        await llm_collection.delete_one({"_id": llm_id, "user_sub": user_sub})
        return llm_id

    @staticmethod
    async def update_conversation_llm(
        user_sub: str,
        conversation_id: str,
        llm_id: str,
    ) -> str:
        """更新对话的LLM"""
        conv_collection = MongoDB.get_collection("conversation")
        llm_collection = MongoDB.get_collection("llm")

        # 如果llm_id为空，则使用系统默认chat模型
        if not llm_id:
            # 查找系统默认chat模型
            config = Config().get_config()
            system_llm = await llm_collection.find_one({
                "user_sub": "",
                "type": "chat",
                "model_name": config.llm.model
            })

            llm_dict = {
                "llm_id": str(system_llm["_id"]),
                "model_name": system_llm["model_name"],
                "icon": system_llm["icon"],
            }
            llm_id = str(system_llm["_id"])  # 更新llm_id为实际的UUID
        else:
            # 查找用户模型或系统模型
            llm_dict = await llm_collection.find_one({
                "$and": [
                    {"_id": llm_id},
                    {"$or": [{"user_sub": user_sub}, {"user_sub": ""}]}
                ]
            })
            if not llm_dict:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise ValueError(err)
            llm_dict = {
                "llm_id": str(llm_dict["_id"]),
                "model_name": llm_dict["model_name"],
                "icon": llm_dict["icon"],
            }
        conv_dict = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not conv_dict:
            err_msg = "[LLMManager] 更新对话的LLM失败，未找到对话"
            logger.error(err_msg)
            raise ValueError(err_msg)

        llm_item = LLMItem(
            llm_id=llm_id,
            model_name=llm_dict["model_name"],
            icon=llm_dict["icon"],
        )
        await conv_collection.update_one(
            {"_id": conversation_id, "user_sub": user_sub},
            {"$set": {"llm": llm_item.model_dump(by_alias=True)}},
        )
        return conversation_id

    @staticmethod
    async def list_embedding_models(user_sub: str = "") -> list[LLMProviderInfo]:
        """
        获取embedding模型列表

        :param user_sub: 用户ID，为空时返回系统级别的模型
        :return: embedding模型列表
        """
        llm_collection = MongoDB.get_collection("llm")

        query = {"type": "embedding", "user_sub": user_sub}

        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)

        llm_list = []
        for llm in result:
            llm_item = LLMManager._create_llm_provider_info(llm)
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def list_all_embedding_models(user_sub: str) -> list[LLMProviderInfo]:
        """
        获取用户可访问的所有embedding模型列表（包括系统模型和用户模型）

        :param user_sub: 用户ID
        :return: embedding模型列表
        """
        llm_collection = MongoDB.get_collection("llm")

        # 使用$or查询同时获取系统模型和用户模型
        query = {
            "type": "embedding",
            "$or": [{"user_sub": ""}, {"user_sub": user_sub}]
        }

        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)

        llm_list = []
        for llm in result:
            llm_item = LLMManager._create_llm_provider_info(llm)
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def list_reranker_models(user_sub: str = "") -> list[LLMProviderInfo]:
        """
        获取reranker模型列表

        :param user_sub: 用户ID，为空时返回系统级别的模型
        :return: reranker模型列表
        """
        llm_collection = MongoDB.get_collection("llm")

        query = {"type": "reranker", "user_sub": user_sub}

        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)

        llm_list = []
        for llm in result:
            llm_item = LLMManager._create_llm_provider_info(llm)
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def list_all_reranker_models(user_sub: str) -> list[LLMProviderInfo]:
        """
        获取用户可访问的所有reranker模型列表（包括系统模型和用户模型）

        :param user_sub: 用户ID
        :return: reranker模型列表
        """
        llm_collection = MongoDB.get_collection("llm")

        # 使用$or查询同时获取系统模型和用户模型
        query = {
            "type": "reranker",
            "$or": [{"user_sub": ""}, {"user_sub": user_sub}]
        }

        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)

        llm_list = []
        for llm in result:
            llm_item = LLMManager._create_llm_provider_info(llm)
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def _init_system_model(model_id: str, model_type: str, model_config: EmbeddingConfig | RerankerConfig | LLMConfig | FunctionCallConfig, title: str):
        """
        初始化系统模型的通用方法

        :param model_type: 模型类型 ('embedding', 'reranker', 'function_call')
        :param model_config: 模型配置对象
        :param title: 模型标题
        """
        # 检查配置是否为空（对于reranker，允许不配置，默认使用jaccard算法）
        if model_type == "reranker":
            # 如果关键字段都为空，则跳过初始化（使用jaccard算法作为默认）
            if not model_config.provider and not model_config.model:
                logger.info(
                    f"[LLMManager] 跳过系统{model_type}模型初始化（将使用jaccard算法作为默认）")
                return

        llm_collection = MongoDB.get_collection("llm")

        # 推断模型能力
        # 优先使用配置文件中明确指定的provider，如果没有则从endpoint推断
        provider = getattr(model_config, 'provider', '') or getattr(
            model_config, 'backend', '') or get_provider_from_endpoint(model_config.endpoint)

        # 根据模型类型选择正确的ModelType
        from apps.llm.model_types import ModelType
        model_type_map = {
            "chat": ModelType.CHAT,
            "embedding": ModelType.EMBEDDING,
            "reranker": ModelType.RERANK,
            "function_call": ModelType.FUNCTION_CALL,
        }
        registry_model_type = model_type_map.get(model_type, ModelType.CHAT)

        # 从model_registry获取完整的模型能力
        capabilities = model_registry.get_model_capabilities(
            provider, model_config.model, registry_model_type)

        # 获取图标
        provider_icon = llm_provider_dict.get(provider, {}).get(
            "icon", getattr(model_config, 'icon', ''))

        # 创建系统模型
        # 对于非chat模型，使用默认值；对于chat模型，从capabilities获取
        system_llm = LLM(
            _id=model_id,
            user_sub="",  # 系统级别模型
            title=title,
            icon=provider_icon,
            openai_base_url=model_config.endpoint,
            openai_api_key=getattr(model_config, 'api_key', ''),
            model_name=model_config.model,
            max_tokens=getattr(model_config, 'max_tokens', None),
            type=[model_type],  # 使用列表格式
            provider=provider,

            # 基础能力 - 使用getattr安全访问，适用于不同类型的能力对象
            supports_streaming=getattr(
                capabilities, 'supports_streaming', True) if capabilities else True,
            supports_function_calling=getattr(
                capabilities, 'supports_function_calling', True) if capabilities else True,
            supports_json_mode=getattr(
                capabilities, 'supports_json_mode', True) if capabilities else True,
            supports_structured_output=getattr(
                capabilities, 'supports_structured_output', False) if capabilities else False,

            # 推理能力
            supports_thinking=getattr(
                capabilities, 'supports_thinking', False) if capabilities else False,
            can_toggle_thinking=getattr(
                capabilities, 'can_toggle_thinking', False) if capabilities else False,
            supports_reasoning_content=getattr(
                capabilities, 'supports_reasoning_content', False) if capabilities else False,

            # 参数支持
            max_tokens_param=getattr(
                capabilities, 'max_tokens_param', "max_tokens") if capabilities else "max_tokens",
            supports_temperature=getattr(
                capabilities, 'supports_temperature', True) if capabilities else True,
            supports_top_p=getattr(
                capabilities, 'supports_top_p', True) if capabilities else True,
            supports_top_k=getattr(
                capabilities, 'supports_top_k', False) if capabilities else False,
            supports_frequency_penalty=getattr(
                capabilities, 'supports_frequency_penalty', False) if capabilities else False,
            supports_presence_penalty=getattr(
                capabilities, 'supports_presence_penalty', False) if capabilities else False,
            supports_min_p=getattr(
                capabilities, 'supports_min_p', False) if capabilities else False,

            # 高级功能
            supports_response_format=getattr(
                capabilities, 'supports_response_format', True) if capabilities else True,
            supports_tools=getattr(
                capabilities, 'supports_tools', True) if capabilities else True,
            supports_tool_choice=getattr(
                capabilities, 'supports_tool_choice', True) if capabilities else True,
            supports_extra_body=getattr(
                capabilities, 'supports_extra_body', True) if capabilities else True,
            supports_stream_options=getattr(
                capabilities, 'supports_stream_options', True) if capabilities else True,

            # 特殊参数
            supports_enable_thinking=getattr(
                capabilities, 'supports_enable_thinking', False) if capabilities else False,
            supports_thinking_budget=getattr(
                capabilities, 'supports_thinking_budget', False) if capabilities else False,
            supports_enable_search=getattr(
                capabilities, 'supports_enable_search', False) if capabilities else False,

            # 其他信息
            notes=getattr(capabilities, 'notes', "") if capabilities else "",
        )

        # 使用by_alias=True将id字段作为_id插入，保持UUID字符串格式
        insert_data = system_llm.model_dump(by_alias=True)
        # 如果模型已存在，则更新，否则插入
        await llm_collection.update_one({"_id": model_id}, {"$set": insert_data}, upsert=True)
        logger.info(f"[LLMManager] 创建系统{model_type}模型: {model_config.model}")

    @staticmethod
    async def get_function_call_model_id(user_sub: str, app_llm_id: str | None = None) -> str | None:
        """
        获取function call场景使用的模型ID

        优先级顺序（从高到低）：
        1. 应用配置的模型 (app_llm_id) - 最高优先级
        2. 用户偏好的 function call 模型
        3. 系统默认的 function call 模型
        4. 系统默认的 chat 模型

        :param user_sub: 用户ID
        :param app_llm_id: 应用配置的模型ID（可选）
        :return: function call模型ID或chat模型ID，如果都不存在则返回None
        """
        try:
            llm_collection = MongoDB.get_collection("llm")

            # 🔑 第一优先级：应用配置的模型（最高优先级）
            if app_llm_id:
                logger.info(f"[LLMManager] 使用应用配置的模型用于函数调用: {app_llm_id}")
                return app_llm_id

            # 第二优先级：获取用户偏好的function call模型
            from apps.services.user import UserManager
            user_preferences = await UserManager.get_user_preferences_by_user_sub(user_sub)

            # 如果用户配置了function call模型偏好，检查该模型是否真正支持函数调用
            if user_preferences.function_call_model_preference:
                llm_id = user_preferences.function_call_model_preference.llm_id
                # 检查该模型是否支持函数调用
                llm_data = await llm_collection.find_one({"_id": llm_id})
                if llm_data:
                    supports_fc = llm_data.get(
                        "supports_function_calling", True)
                    if supports_fc:
                        logger.info(
                            f"[LLMManager] 使用用户偏好的function call模型: {llm_id}")
                        return llm_id
                    else:
                        logger.warning(
                            f"[LLMManager] 用户偏好的模型 {llm_id} 不支持函数调用，将使用其他模型")

            # 第三优先级：获取系统默认的function call模型
            # 注意：type字段可能是数组或字符串，需要同时支持两种格式
            system_function_call_model = await llm_collection.find_one({
                "user_sub": "",
                "$or": [
                    {"type": "function_call"},  # 兼容字符串格式
                    {"type": {"$in": ["function_call"]}}  # 兼容数组格式
                ],
                "supports_function_calling": True  # 确保支持函数调用
            })

            if system_function_call_model:
                llm_id = str(system_function_call_model["_id"])
                logger.info(f"[LLMManager] 使用系统默认的function call模型: {llm_id}")
                return llm_id

            # 第四优先级：如果没有专门的function call模型，尝试找支持函数调用的chat模型
            logger.warning(
                "[LLMManager] 未找到专门的function call模型，寻找支持函数调用的chat模型")
            system_chat_with_fc = await llm_collection.find_one({
                "user_sub": "",
                "$or": [
                    {"type": "chat"},  # 兼容字符串格式
                    {"type": {"$in": ["chat"]}}  # 兼容数组格式
                ],
                "supports_function_calling": True
            })

            if system_chat_with_fc:
                llm_id = str(system_chat_with_fc["_id"])
                logger.info(f"[LLMManager] 使用支持函数调用的chat模型: {llm_id}")
                return llm_id

            # 最后降级：使用系统默认的chat模型
            logger.warning("[LLMManager] 未找到支持函数调用的模型，降级使用系统默认的chat模型")
            config = Config().get_config()
            system_chat_model = await llm_collection.find_one({
                "user_sub": "",
                "$or": [
                    {"type": "chat"},  # 兼容字符串格式
                    {"type": {"$in": ["chat"]}}  # 兼容数组格式
                ],
                "model_name": config.llm.model
            })

            if system_chat_model:
                llm_id = str(system_chat_model["_id"])
                logger.info(f"[LLMManager] 降级使用系统默认的chat模型: {llm_id}")
                return llm_id

            logger.error("[LLMManager] 未找到任何可用的模型")
            return None

        except Exception as e:
            logger.error(f"[LLMManager] 获取模型失败: {e}")
            return None

    @staticmethod
    async def init_system_models():
        """
        初始化系统模型（从配置文件读取embedding、reranker和function_call配置并插入数据库）
        在初始化之前，先清理所有系统模型
        """
        config = Config().get_config()
        llm_collection = MongoDB.get_collection("llm")

        # 清理所有系统模型（user_sub为空的模型）
        delete_result = await llm_collection.delete_many({"user_sub": ""})
        logger.info(f"[LLMManager] 清理了 {delete_result.deleted_count} 个旧系统模型")

        # 初始化embedding模型
        await LLMManager._init_system_model(
            DefaultModelId.DEFAULT_EMBEDDING_MODEL_ID.value,
            "embedding",
            config.embedding,
            "System Embedding Model"
        )

        # 初始化reranker模型
        await LLMManager._init_system_model(
            DefaultModelId.DEFAULT_RERANKER_MODEL_ID.value,
            "reranker",
            config.reranker,
            "System Reranker Model"
        )
        # 初始化chat模型
        await LLMManager._init_system_model(
            DefaultModelId.DEFAULT_CHAT_MODEL_ID.value,
            "chat",
            config.llm,
            "System Chat Model"
        )
        # 初始化function_call模型
        await LLMManager._init_system_model(
            DefaultModelId.DEFAULT_FUNCTION_CALL_MODEL_ID.value,
            "function_call",
            config.function_call,
            "System Function Call Model"
        )

    @staticmethod
    async def get_model_capabilities(user_sub: str, llm_id: str) -> dict:
        """
        获取指定模型支持的参数配置项

        :param user_sub: 用户ID
        :param llm_id: 模型ID
        :return: 模型能力配置字典
        """
        from apps.llm.model_types import ModelType

        # 获取模型信息（支持系统模型和用户模型）
        llm_collection = MongoDB.get_collection("llm")

        result = await llm_collection.find_one({
            "_id": llm_id,
            "$or": [{"user_sub": user_sub}, {"user_sub": ""}]
        })

        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在或无权限访问"
            logger.error(err)
            raise ValueError(err)

        llm = LLM.model_validate(result)

        # 从注册表获取模型能力
        provider = llm.provider or get_provider_from_endpoint(
            llm.openai_base_url)
        capabilities = model_registry.get_model_capabilities(
            provider, llm.model_name, ModelType.CHAT)

        # 构建参数配置项响应
        result_dict = {
            "provider": provider,
            "modelName": llm.model_name,
            "modelType": "chat",

            # 基础参数支持
            "supportsTemperature": capabilities.supports_temperature if capabilities else True,
            "supportsTopP": capabilities.supports_top_p if capabilities else True,
            "supportsTopK": capabilities.supports_top_k if capabilities else False,
            "supportsFrequencyPenalty": capabilities.supports_frequency_penalty if capabilities else False,
            "supportsPresencePenalty": capabilities.supports_presence_penalty if capabilities else False,
            "supportsMinP": capabilities.supports_min_p if capabilities else False,

            # 高级功能
            "supportsThinking": capabilities.supports_thinking if capabilities else False,
            "canToggleThinking": capabilities.can_toggle_thinking if capabilities else False,
            "supportsEnableSearch": capabilities.supports_enable_search if capabilities else False,
            "supportsFunctionCalling": capabilities.supports_function_calling if capabilities else True,
            "supportsJsonMode": capabilities.supports_json_mode if capabilities else True,
            "supportsStructuredOutput": capabilities.supports_structured_output if capabilities else False,

            # 上下文支持（所有chat模型都支持）
            "supportsContext": True,

            # 参数名称
            "maxTokensParam": capabilities.max_tokens_param if capabilities else "max_tokens",

            # 备注信息
            "notes": llm.notes or ""
        }

        return result_dict
