# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging

from apps.common.config import Config
from apps.common.mongo import MongoDB
from apps.schemas.collection import LLM, LLMItem
from apps.schemas.request_data import (
    UpdateLLMReq,
)
from apps.schemas.response_data import LLMProvider, LLMProviderInfo
from apps.templates.generate_llm_operator_config import llm_provider_dict
from apps.llm.model_registry import model_registry
from apps.llm.adapters import get_provider_from_endpoint

logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""

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
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
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
        from bson import ObjectId
        
        llm_collection = MongoDB().get_collection("llm")
        
        # 尝试同时使用字符串和ObjectId查询，以兼容不同的存储格式
        result = None
        try:
            # 首先尝试作为字符串查询
            result = await llm_collection.find_one({"_id": llm_id})
            
            # 如果字符串查询失败，尝试转换为ObjectId查询
            if not result and ObjectId.is_valid(llm_id):
                result = await llm_collection.find_one({"_id": ObjectId(llm_id)})
                
        except Exception as e:
            logger.warning(f"[LLMManager] 查询LLM时发生错误: {e}")
        
        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)
        
        # 将ObjectId转换为字符串，以兼容LLM模型的验证
        if isinstance(result.get("_id"), ObjectId):
            result["_id"] = str(result["_id"])
            
        return LLM.model_validate(result)

    @staticmethod
    async def get_llm_by_user_sub_and_id(user_sub: str, llm_id: str) -> LLM:
        """
        通过ID获取大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        from bson import ObjectId
        
        llm_collection = MongoDB().get_collection("llm")
        
        # 尝试同时使用字符串和ObjectId查询，以兼容不同的存储格式
        result = None
        try:
            # 首先尝试作为字符串查询
            result = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            
            # 如果字符串查询失败，尝试转换为ObjectId查询
            if not result and ObjectId.is_valid(llm_id):
                result = await llm_collection.find_one({"_id": ObjectId(llm_id), "user_sub": user_sub})
                
        except Exception as e:
            logger.warning(f"[LLMManager] 查询LLM时发生错误: {e}")
        
        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在"
            logger.error(err)
            raise ValueError(err)
        
        # 将ObjectId转换为字符串，以兼容LLM模型的验证
        if isinstance(result.get("_id"), ObjectId):
            result["_id"] = str(result["_id"])
            
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
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")

        # 构建查询条件：包含用户模型和系统模型
        base_query = {"$or": [{"user_sub": user_sub}, {"user_sub": ""}]}
        if llm_id:
            base_query["llm_id"] = llm_id
        if model_type:
            # 支持type字段既可以是字符串也可以是数组
            base_query["type"] = model_type
        
        result = await llm_collection.find(base_query).sort({"created_at": 1}).to_list(length=None)

        llm_list = []
        
        # 只有查询chat类型或者没有指定类型时，才检查并创建默认模型
        if not model_type or model_type == 'chat':
            # 检查是否已存在系统默认chat模型
            config = Config().get_config()
            existing_default = await llm_collection.find_one({
                "user_sub": "",
                "type": "chat",
                "model_name": config.llm.model
            })
            
            if not existing_default:
                # 如果不存在，创建系统默认chat模型
                await LLMManager.init_system_chat_model()
                # 重新查询以包含新创建的模型
                result = await llm_collection.find(base_query).sort({"created_at": 1}).to_list(length=None)

        for llm in result:
            # 标准化type字段为列表格式
            llm_type = llm.get("type", "chat")
            if isinstance(llm_type, str):
                llm_type = [llm_type]
            
            llm_item = LLMProviderInfo(
                llmId=str(llm["_id"]),  # 转换ObjectId为字符串
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
                isEditable=bool(llm.get("user_sub")),  # 系统模型（user_sub=""）不可编辑
                type=llm_type,  # 始终返回列表格式
                # 模型能力字段
                provider=llm.get("provider", ""),
                supportsThinking=llm.get("supports_thinking", False),
                canToggleThinking=llm.get("can_toggle_thinking", False),
                supportsFunctionCalling=llm.get("supports_function_calling", True),
                supportsJsonMode=llm.get("supports_json_mode", True),
                supportsStructuredOutput=llm.get("supports_structured_output", False),
                maxTokensParam=llm.get("max_tokens_param", "max_tokens"),
                notes=llm.get("notes", ""),
            )
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
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")

        # 推断模型能力
        provider = req.provider or get_provider_from_endpoint(req.openai_base_url)
        model_info = model_registry.get_model_info(provider, req.model_name)
        
        # 标准化type字段为列表格式
        model_type = req.type
        if isinstance(model_type, str):
            model_type = [model_type]
        
        # 使用请求中的能力信息，如果没有则从model_registry获取，最后使用默认值
        capabilities = {
            "provider": provider,
            "supports_thinking": req.supports_thinking if req.supports_thinking is not None else (model_info.supports_thinking if model_info else False),
            "can_toggle_thinking": req.can_toggle_thinking if req.can_toggle_thinking is not None else (model_info.can_toggle_thinking if model_info else False),
            "supports_function_calling": req.supports_function_calling if req.supports_function_calling is not None else (model_info.supports_function_calling if model_info else True),
            "supports_json_mode": req.supports_json_mode if req.supports_json_mode is not None else (model_info.supports_json_mode if model_info else True),
            "supports_structured_output": req.supports_structured_output if req.supports_structured_output is not None else (model_info.supports_structured_output if model_info else False),
            "max_tokens_param": req.max_tokens_param or (model_info.max_tokens_param if model_info else "max_tokens"),
            "notes": req.notes or (model_info.notes if model_info else ""),
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

        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        conv_collection = mongo.get_collection("conversation")

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
            
            if not system_llm:
                # 如果系统模型不存在，创建它
                await LLMManager.init_system_chat_model()
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
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
        llm_collection = mongo.get_collection("llm")

        # 如果llm_id为空，则使用系统默认chat模型
        if not llm_id:
            # 查找系统默认chat模型
            config = Config().get_config()
            system_llm = await llm_collection.find_one({
                "user_sub": "",
                "type": "chat",
                "model_name": config.llm.model
            })
            
            if not system_llm:
                # 如果系统模型不存在，创建它
                await LLMManager.init_system_chat_model()
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
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        query = {"type": "embedding", "user_sub": user_sub}
        
        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)
        
        llm_list = []
        for llm in result:
            # 标准化type字段为列表格式
            llm_type = llm.get("type", "embedding")
            if isinstance(llm_type, str):
                llm_type = [llm_type]
            
            llm_item = LLMProviderInfo(
                llmId=str(llm["_id"]),  # 转换ObjectId为字符串
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
                isEditable=bool(llm.get("user_sub")),  # 有user_sub的是用户创建的，可编辑
                type=llm_type,
            )
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def list_all_embedding_models(user_sub: str) -> list[LLMProviderInfo]:
        """
        获取用户可访问的所有embedding模型列表（包括系统模型和用户模型）
        
        :param user_sub: 用户ID
        :return: embedding模型列表
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        # 使用$or查询同时获取系统模型和用户模型
        query = {
            "type": "embedding",
            "$or": [{"user_sub": ""}, {"user_sub": user_sub}]
        }
        
        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)
        
        llm_list = []
        for llm in result:
            # 标准化type字段为列表格式
            llm_type = llm.get("type", "embedding")
            if isinstance(llm_type, str):
                llm_type = [llm_type]
            
            llm_item = LLMProviderInfo(
                llmId=str(llm["_id"]),  # 转换ObjectId为字符串
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
                isEditable=bool(llm.get("user_sub")),  # 系统模型（user_sub=""）不可编辑
                type=llm_type,
            )
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def list_reranker_models(user_sub: str = "") -> list[LLMProviderInfo]:
        """
        获取reranker模型列表
        
        :param user_sub: 用户ID，为空时返回系统级别的模型
        :return: reranker模型列表
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        query = {"type": "reranker", "user_sub": user_sub}
        
        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)
        
        llm_list = []
        for llm in result:
            # 标准化type字段为列表格式
            llm_type = llm.get("type", "reranker")
            if isinstance(llm_type, str):
                llm_type = [llm_type]
            
            llm_item = LLMProviderInfo(
                llmId=str(llm["_id"]),  # 转换ObjectId为字符串
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
                isEditable=bool(llm.get("user_sub")),  # 有user_sub的是用户创建的，可编辑
                type=llm_type,
            )
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def list_all_reranker_models(user_sub: str) -> list[LLMProviderInfo]:
        """
        获取用户可访问的所有reranker模型列表（包括系统模型和用户模型）
        
        :param user_sub: 用户ID
        :return: reranker模型列表
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        # 使用$or查询同时获取系统模型和用户模型
        query = {
            "type": "reranker",
            "$or": [{"user_sub": ""}, {"user_sub": user_sub}]
        }
        
        result = await llm_collection.find(query).sort({"created_at": 1}).to_list(length=None)
        
        llm_list = []
        for llm in result:
            # 标准化type字段为列表格式
            llm_type = llm.get("type", "reranker")
            if isinstance(llm_type, str):
                llm_type = [llm_type]
            
            llm_item = LLMProviderInfo(
                llmId=str(llm["_id"]),  # 转换ObjectId为字符串
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
                isEditable=bool(llm.get("user_sub")),  # 系统模型（user_sub=""）不可编辑
                type=llm_type,
            )
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def init_system_chat_model():
        """初始化系统级别的chat模型"""
        config = Config().get_config()
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        # 推断chat模型能力
        # 优先使用配置文件中明确指定的provider，如果没有则从endpoint推断
        provider = getattr(config.llm, 'provider', '') or get_provider_from_endpoint(config.llm.endpoint)
        model_info = model_registry.get_model_info(provider, config.llm.model)
        
        # 根据provider获取图标
        provider_icon = llm_provider_dict.get(provider, {}).get("icon", "")
        
        # 创建系统chat模型
        chat_llm = LLM(
            user_sub="",  # 系统级别模型
            title="System Chat Model",
            icon=provider_icon,
            openai_api_key=config.llm.key,
            openai_base_url=config.llm.endpoint,
            model_name=config.llm.model,
            max_tokens=config.llm.max_tokens or (model_info.max_tokens_param if model_info else 8192),
            type=['chat'],  # 使用列表格式
            provider=provider,
            supports_thinking=model_info.supports_thinking if model_info else False,
            can_toggle_thinking=model_info.can_toggle_thinking if model_info else False,
            supports_function_calling=model_info.supports_function_calling if model_info else False,
            supports_json_mode=model_info.supports_json_mode if model_info else False,
            supports_structured_output=model_info.supports_structured_output if model_info else False,
            max_tokens_param=model_info.max_tokens_param if model_info else None,
            notes=model_info.notes if model_info else "",
        )
        
        # 排除_id字段让MongoDB自动生成_id，避免冲突
        insert_data = chat_llm.model_dump(exclude={"_id"})
        await llm_collection.insert_one(insert_data)
        logger.info(f"已初始化系统chat模型: {config.llm.model}")

    @staticmethod
    async def _init_system_model(model_type: str, model_config, title: str):
        """
        初始化系统模型的通用方法
        
        :param model_type: 模型类型 ('embedding', 'reranker', 'function_call')
        :param model_config: 模型配置对象
        :param title: 模型标题
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        # 推断模型能力
        # 优先使用配置文件中明确指定的provider，如果没有则从endpoint推断
        provider = getattr(model_config, 'provider', '') or getattr(model_config, 'backend', '') or get_provider_from_endpoint(model_config.endpoint)
        model_info = model_registry.get_model_info(provider, model_config.model)
        
        # 根据provider获取图标，如果没有则使用配置文件中的图标
        provider_icon = llm_provider_dict.get(provider, {}).get("icon", getattr(model_config, 'icon', ''))
        
        # 创建系统模型
        system_llm = LLM(
            user_sub="",  # 系统级别模型
            title=title,
            icon=provider_icon,
            openai_base_url=model_config.endpoint,
            openai_api_key=getattr(model_config, 'api_key', ''),
            model_name=model_config.model,
            max_tokens=getattr(model_config, 'max_tokens', None),
            type=[model_type],  # 使用列表格式
            provider=provider,
            supports_thinking=model_info.supports_thinking if model_info else False,
            can_toggle_thinking=model_info.can_toggle_thinking if model_info else False,
            supports_function_calling=model_info.supports_function_calling if model_info else True,
            supports_json_mode=model_info.supports_json_mode if model_info else True,
            supports_structured_output=model_info.supports_structured_output if model_info else False,
            max_tokens_param=model_info.max_tokens_param if model_info else "max_tokens",
            notes=model_info.notes if model_info else "",
        )
        
        # 使用upsert模式：如果model_name已存在就更新，否则插入
        filter_query = {
            "user_sub": "",
            "model_name": model_config.model
        }
        
        # 排除id和_id字段以避免MongoDB的不可变_id字段错误
        model_data = system_llm.model_dump(by_alias=True, exclude={"id", "_id"})
        
        # 使用update_one替代replace_one，更安全
        result = await llm_collection.update_one(
            filter_query,
            {"$set": model_data},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"[LLMManager] 创建系统{model_type}模型: {model_config.model}")
        else:
            logger.info(f"[LLMManager] 更新系统{model_type}模型: {model_config.model}")

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
            mongo = MongoDB()
            llm_collection = mongo.get_collection("llm")
            
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
                    supports_fc = llm_data.get("supports_function_calling", True)
                    if supports_fc:
                        logger.info(f"[LLMManager] 使用用户偏好的function call模型: {llm_id}")
                        return llm_id
                    else:
                        logger.warning(f"[LLMManager] 用户偏好的模型 {llm_id} 不支持函数调用，将使用其他模型")
            
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
            logger.warning("[LLMManager] 未找到专门的function call模型，寻找支持函数调用的chat模型")
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
            
            if not system_chat_model:
                # 如果系统chat模型不存在，创建它
                await LLMManager.init_system_chat_model()
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
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        # 清理所有系统模型（user_sub为空的模型）
        delete_result = await llm_collection.delete_many({"user_sub": ""})
        logger.info(f"[LLMManager] 清理了 {delete_result.deleted_count} 个旧系统模型")
        
        # 初始化embedding模型
        await LLMManager._init_system_model(
            "embedding", 
            config.embedding, 
            "System Embedding Model"
        )
        
        # 初始化reranker模型
        await LLMManager._init_system_model(
            "reranker", 
            config.reranker, 
            "System Reranker Model"
        )
        
        # 初始化function_call模型
        await LLMManager._init_system_model(
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
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")
        
        # 尝试将llm_id转换为ObjectId（如果适用）
        from bson import ObjectId
        from bson.errors import InvalidId
        
        # 先尝试作为字符串查询，如果失败再尝试ObjectId
        try:
            # 首先尝试作为字符串ID查询（UUID格式）
            result = await llm_collection.find_one({
                "_id": llm_id,
                "$or": [{"user_sub": user_sub}, {"user_sub": ""}]
            })
            
            # 如果没找到且llm_id可以转换为ObjectId，则尝试作为ObjectId查询
            if not result and ObjectId.is_valid(llm_id):
                result = await llm_collection.find_one({
                    "_id": ObjectId(llm_id),
                    "$or": [{"user_sub": user_sub}, {"user_sub": ""}]
                })
        except InvalidId:
            result = None
        
        if not result:
            err = f"[LLMManager] LLM {llm_id} 不存在或无权限访问"
            logger.error(err)
            raise ValueError(err)
        
        # 将ObjectId转换为字符串，以兼容LLM模型的验证
        if isinstance(result.get("_id"), ObjectId):
            result["_id"] = str(result["_id"])
        
        llm = LLM.model_validate(result)
        
        # 从注册表获取模型能力
        provider = llm.provider or get_provider_from_endpoint(llm.openai_base_url)
        capabilities = model_registry.get_model_capabilities(provider, llm.model_name, ModelType.CHAT)
        
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
