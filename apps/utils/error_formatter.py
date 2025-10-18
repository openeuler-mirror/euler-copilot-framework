# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""错误格式化工具"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ErrorFormatter:
    """错误信息格式化器"""
    
    # 错误类型到用户友好消息的映射
    ERROR_MESSAGES = {
        # API相关错误
        "AuthenticationError": "身份验证失败，请检查API密钥配置",
        "PaymentRequired": "账户余额不足，请充值后重试",
        "RateLimitError": "请求频率过高，请稍后重试",
        "ConnectionError": "网络连接失败，请检查网络设置",
        "TimeoutError": "请求超时，请稍后重试",
        
        # 业务逻辑错误
        "ValidationError": "请求参数不正确",
        "PermissionError": "权限不足，无法执行此操作",
        "NotFoundError": "请求的资源不存在",
        
        # 系统错误
        "InternalServerError": "系统内部错误，请稍后重试",
        "ServiceUnavailable": "服务暂时不可用，请稍后重试",
    }
    
    # 错误代码到建议操作的映射
    ERROR_SUGGESTIONS = {
        401: "请检查登录状态或API密钥配置",
        402: "请前往控制台充值账户余额",
        403: "请联系管理员获取相应权限",
        404: "请检查请求的资源是否存在",
        429: "请降低请求频率或稍后重试",
        500: "请稍后重试，如问题持续存在请联系技术支持",
        502: "服务网关错误，请稍后重试",
        503: "服务暂时不可用，请稍后重试",
        504: "服务响应超时，请稍后重试",
    }
    
    @classmethod
    def format_error_for_frontend(
        cls, 
        error_code: int, 
        error_message: str, 
        error_type: Optional[str] = None,
        error_details: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        格式化错误信息供前端显示
        
        Args:
            error_code: HTTP状态码
            error_message: 错误消息
            error_type: 错误类型
            error_details: 错误详情
            
        Returns:
            格式化后的错误信息字典
        """
        
        # 获取用户友好的错误消息
        user_message = error_message
        if error_type and error_type in cls.ERROR_MESSAGES:
            user_message = cls.ERROR_MESSAGES[error_type]
        
        # 获取建议操作
        suggestion = cls.ERROR_SUGGESTIONS.get(error_code, "请稍后重试")
        
        # 确定错误级别
        if error_code >= 500:
            level = "error"
        elif error_code >= 400:
            level = "warning"
        else:
            level = "info"
        
        # 构建返回结果
        result = {
            "code": error_code,
            "message": user_message,
            "level": level,
            "suggestion": suggestion,
            "timestamp": None,  # 前端会自动添加时间戳
        }
        
        # 添加原始错误信息（用于调试）
        if error_message != user_message:
            result["original_message"] = error_message
        
        # 添加错误类型
        if error_type:
            result["type"] = error_type
        
        # 添加详细信息（如验证错误的具体字段）
        if error_details:
            result["details"] = error_details
        
        return result
    
    @classmethod
    def format_llm_error(cls, error_message: str) -> Dict[str, Any]:
        """
        格式化LLM相关错误
        
        Args:
            error_message: 错误消息
            
        Returns:
            格式化后的错误信息
        """
        
        # 根据错误消息内容判断错误类型
        error_code = 500
        error_type = "InternalServerError"
        suggestion = "请稍后重试"
        
        message_lower = error_message.lower()
        
        if "认证失败" in message_lower or "api密钥" in message_lower:
            error_code = 401
            error_type = "AuthenticationError"
            suggestion = "请检查API密钥配置是否正确"
        elif "余额不足" in message_lower or "欠费" in message_lower:
            error_code = 402
            error_type = "PaymentRequired"
            suggestion = "请前往阿里云控制台充值账户余额"
        elif "频率超限" in message_lower or "限制" in message_lower:
            error_code = 429
            error_type = "RateLimitError"
            suggestion = "请降低请求频率或稍后重试"
        elif "连接" in message_lower or "网络" in message_lower:
            error_code = 503
            error_type = "ConnectionError"
            suggestion = "请检查网络连接或服务状态"
        elif "超时" in message_lower:
            error_code = 504
            error_type = "TimeoutError"
            suggestion = "请稍后重试，如问题持续存在请联系技术支持"
        
        return cls.format_error_for_frontend(
            error_code=error_code,
            error_message=error_message,
            error_type=error_type
        )
    
    @classmethod
    def create_error_response(cls, error_info: Dict[str, Any]) -> str:
        """
        创建错误响应文本（用于流式响应）
        
        Args:
            error_info: 错误信息字典
            
        Returns:
            格式化的错误响应文本
        """
        
        message = error_info.get("message", "发生未知错误")
        suggestion = error_info.get("suggestion", "")
        
        error_text = f"❌ {message}"
        if suggestion:
            error_text += f"\n\n💡 建议: {suggestion}"
        
        return error_text
