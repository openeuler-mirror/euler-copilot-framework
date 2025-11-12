from enum import Enum


class DefaultModelId(str, Enum):
    DEFAULT_EMBEDDING_MODEL_ID = "default-embedding-model_id"
    DEFAULT_RERANKER_MODEL_ID = "default-reranker-model_id"
    DEFAULT_CHAT_MODEL_ID = "default-chat-model_id"
    DEFAULT_FUNCTION_CALL_MODEL_ID = "default-function-call-model_id"
