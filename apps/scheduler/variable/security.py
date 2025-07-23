# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""变量安全管理模块

提供密钥变量的额外安全保障，包括：
- 访问审计日志
- 密钥轮换
- 安全检查
- 权限验证
"""

import logging
import hashlib
import time
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, UTC, timedelta
from dataclasses import dataclass

from apps.common.mongo import MongoDB

logger = logging.getLogger(__name__)


@dataclass
class AccessLog:
    """访问日志记录"""
    variable_name: str
    user_sub: str
    access_time: datetime
    access_type: str  # read, write, delete
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class SecretVariableSecurity:
    """密钥变量安全管理器"""
    
    def __init__(self):
        """初始化安全管理器"""
        self._access_logs: List[AccessLog] = []
        self._failed_access_attempts: Dict[str, List[datetime]] = {}
        self._blocked_users: Set[str] = set()
        
        # 安全配置
        self.max_failed_attempts = 5  # 最大失败尝试次数
        self.block_duration_minutes = 30  # 封禁时长（分钟）
        self.audit_retention_days = 90  # 审计日志保留天数
    
    async def verify_access_permission(self, 
                                     variable_name: str,
                                     user_sub: str,
                                     access_type: str = "read",
                                     ip_address: Optional[str] = None) -> bool:
        """验证访问权限
        
        Args:
            variable_name: 变量名
            user_sub: 用户ID
            access_type: 访问类型（read, write, delete）
            ip_address: IP地址
            
        Returns:
            bool: 是否允许访问
        """
        try:
            # 检查用户是否被封禁
            if await self._is_user_blocked(user_sub):
                await self._log_access(
                    variable_name, user_sub, access_type, ip_address,
                    success=False, error_message="用户被临时封禁"
                )
                return False
            
            # 检查是否超出访问频率限制
            if await self._check_rate_limit(user_sub):
                await self._log_access(
                    variable_name, user_sub, access_type, ip_address,
                    success=False, error_message="访问频率过高"
                )
                await self._record_failed_attempt(user_sub)
                return False
            
            # 验证IP地址（可选）
            if ip_address and not await self._is_ip_allowed(ip_address):
                await self._log_access(
                    variable_name, user_sub, access_type, ip_address,
                    success=False, error_message="IP地址不在允许列表中"
                )
                return False
            
            # 记录成功访问
            await self._log_access(variable_name, user_sub, access_type, ip_address)
            await self._clear_failed_attempts(user_sub)
            
            return True
            
        except Exception as e:
            logger.error(f"验证访问权限失败: {e}")
            return False
    
    async def audit_secret_access(self, 
                                 variable_name: str,
                                 user_sub: str,
                                 actual_value: str,
                                 access_type: str = "read") -> None:
        """审计密钥访问
        
        Args:
            variable_name: 变量名
            user_sub: 用户ID
            actual_value: 实际访问的值
            access_type: 访问类型
        """
        try:
            # 计算值的哈希（用于审计，不存储原始值）
            value_hash = hashlib.sha256(actual_value.encode()).hexdigest()[:16]
            
            # 记录详细的审计信息
            audit_record = {
                "variable_name": variable_name,
                "user_sub": user_sub,
                "access_time": datetime.now(UTC),
                "access_type": access_type,
                "value_hash": value_hash,
                "value_length": len(actual_value),
            }
            
            # 保存到审计日志
            await self._save_audit_record(audit_record)
            
            logger.info(f"已审计密钥访问: {variable_name} by {user_sub}")
            
        except Exception as e:
            logger.error(f"审计密钥访问失败: {e}")
    
    async def check_secret_strength(self, secret_value: str) -> Dict[str, Any]:
        """检查密钥强度
        
        Args:
            secret_value: 密钥值
            
        Returns:
            Dict[str, Any]: 检查结果
        """
        result = {
            "is_strong": False,
            "score": 0,
            "warnings": [],
            "recommendations": []
        }
        
        try:
            # 长度检查
            if len(secret_value) < 8:
                result["warnings"].append("密钥长度过短（建议至少8位）")
            elif len(secret_value) >= 12:
                result["score"] += 2
            else:
                result["score"] += 1
            
            # 复杂性检查
            has_upper = any(c.isupper() for c in secret_value)
            has_lower = any(c.islower() for c in secret_value)
            has_digit = any(c.isdigit() for c in secret_value)
            has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in secret_value)
            
            complexity_score = sum([has_upper, has_lower, has_digit, has_special])
            result["score"] += complexity_score
            
            if complexity_score < 3:
                result["recommendations"].append("建议包含大小写字母、数字和特殊字符")
            
            # 常见密码检查
            common_passwords = ["password", "123456", "admin", "root", "qwerty"]
            if secret_value.lower() in common_passwords:
                result["warnings"].append("使用了常见的弱密码")
                result["score"] = 0
            
            # 重复字符检查
            if len(set(secret_value)) < len(secret_value) * 0.6:
                result["warnings"].append("包含过多重复字符")
            
            # 设置强度等级
            if result["score"] >= 6 and len(result["warnings"]) == 0:
                result["is_strong"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"检查密钥强度失败: {e}")
            return result
    
    async def rotate_secret_key(self, variable_name: str, user_sub: str) -> bool:
        """轮换密钥的加密密钥
        
        Args:
            variable_name: 变量名
            user_sub: 用户ID
            
        Returns:
            bool: 是否轮换成功
        """
        try:
            from .pool_manager import get_pool_manager
            from .type import VariableScope
            
            pool_manager = await get_pool_manager()
            
            # 获取用户变量池
            user_pool = await pool_manager.get_user_pool(user_sub)
            if not user_pool:
                logger.error(f"用户变量池不存在: {user_sub}")
                return False
            
            # 获取密钥变量
            variable = await user_pool.get_variable(variable_name)
            if not variable or not variable.var_type.is_secret_type():
                return False
            
            # 获取原始值
            original_value = variable.value
            
            # 重新生成加密密钥并重新加密
            variable._encryption_key = variable._generate_encryption_key()
            variable.value = original_value  # 这会触发重新加密
            
            # 更新存储
            await user_pool._persist_variable(variable)
            
            # 记录轮换操作
            await self._log_access(
                variable_name, user_sub, "key_rotation", 
                success=True, error_message="密钥轮换成功"
            )
            
            logger.info(f"已轮换密钥变量的加密密钥: {variable_name}")
            return True
            
        except Exception as e:
            logger.error(f"轮换密钥失败: {e}")
            return False
    
    async def get_access_logs(self, 
                             variable_name: Optional[str] = None,
                             user_sub: Optional[str] = None,
                             hours: int = 24) -> List[Dict[str, Any]]:
        """获取访问日志
        
        Args:
            variable_name: 变量名（可选）
            user_sub: 用户ID（可选）
            hours: 查询最近几小时的日志
            
        Returns:
            List[Dict[str, Any]]: 访问日志列表
        """
        try:
            collection = MongoDB().get_collection("variable_access_logs")
            
            # 构建查询条件
            query = {
                "access_time": {
                    "$gte": datetime.now(UTC) - timedelta(hours=hours)
                }
            }
            
            if variable_name:
                query["variable_name"] = variable_name
            if user_sub:
                query["user_sub"] = user_sub
            
            # 查询日志
            logs = []
            async for doc in collection.find(query).sort("access_time", -1):
                logs.append({
                    "variable_name": doc.get("variable_name"),
                    "user_sub": doc.get("user_sub"),
                    "access_time": doc.get("access_time"),
                    "access_type": doc.get("access_type"),
                    "ip_address": doc.get("ip_address"),
                    "success": doc.get("success", True),
                    "error_message": doc.get("error_message")
                })
            
            return logs
            
        except Exception as e:
            logger.error(f"获取访问日志失败: {e}")
            return []
    
    async def _is_user_blocked(self, user_sub: str) -> bool:
        """检查用户是否被封禁"""
        if user_sub not in self._failed_access_attempts:
            return False
        
        failed_attempts = self._failed_access_attempts[user_sub]
        recent_failures = [
            attempt for attempt in failed_attempts
            if attempt > datetime.now(UTC) - timedelta(minutes=self.block_duration_minutes)
        ]
        
        return len(recent_failures) >= self.max_failed_attempts
    
    async def _check_rate_limit(self, user_sub: str) -> bool:
        """检查访问频率限制"""
        try:
            # 获取最近1分钟的访问记录
            collection = MongoDB().get_collection("variable_access_logs")
            count = await collection.count_documents({
                "user_sub": user_sub,
                "access_time": {
                    "$gte": datetime.now(UTC) - timedelta(minutes=1)
                }
            })
            
            # 限制每分钟最多30次访问
            return count >= 30
            
        except Exception as e:
            logger.error(f"检查访问频率失败: {e}")
            return False
    
    async def _is_ip_allowed(self, ip_address: str) -> bool:
        """检查IP地址是否被允许"""
        # 这里可以实现IP白名单/黑名单逻辑
        # 暂时返回True，表示允许所有IP
        return True
    
    async def _record_failed_attempt(self, user_sub: str):
        """记录失败尝试"""
        if user_sub not in self._failed_access_attempts:
            self._failed_access_attempts[user_sub] = []
        
        self._failed_access_attempts[user_sub].append(datetime.now(UTC))
        
        # 清理过期的失败记录
        cutoff_time = datetime.now(UTC) - timedelta(minutes=self.block_duration_minutes)
        self._failed_access_attempts[user_sub] = [
            attempt for attempt in self._failed_access_attempts[user_sub]
            if attempt > cutoff_time
        ]
    
    async def _clear_failed_attempts(self, user_sub: str):
        """清除失败尝试记录"""
        if user_sub in self._failed_access_attempts:
            del self._failed_access_attempts[user_sub]
    
    async def _log_access(self, 
                         variable_name: str,
                         user_sub: str,
                         access_type: str,
                         ip_address: Optional[str] = None,
                         success: bool = True,
                         error_message: Optional[str] = None):
        """记录访问日志"""
        try:
            log_entry = {
                "variable_name": variable_name,
                "user_sub": user_sub,
                "access_time": datetime.now(UTC),
                "access_type": access_type,
                "ip_address": ip_address,
                "success": success,
                "error_message": error_message
            }
            
            # 保存到数据库
            collection = MongoDB().get_collection("variable_access_logs")
            await collection.insert_one(log_entry)
            
        except Exception as e:
            logger.error(f"记录访问日志失败: {e}")
    
    async def _save_audit_record(self, audit_record: Dict[str, Any]):
        """保存审计记录"""
        try:
            collection = MongoDB().get_collection("variable_audit_logs")
            await collection.insert_one(audit_record)
        except Exception as e:
            logger.error(f"保存审计记录失败: {e}")
    
    async def cleanup_old_logs(self):
        """清理过期的日志记录"""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(days=self.audit_retention_days)
            
            # 清理访问日志
            access_collection = MongoDB().get_collection("variable_access_logs")
            result1 = await access_collection.delete_many({
                "access_time": {"$lt": cutoff_time}
            })
            
            # 清理审计日志
            audit_collection = MongoDB().get_collection("variable_audit_logs")
            result2 = await audit_collection.delete_many({
                "access_time": {"$lt": cutoff_time}
            })
            
            logger.info(f"已清理过期日志: 访问日志 {result1.deleted_count} 条, 审计日志 {result2.deleted_count} 条")
            
        except Exception as e:
            logger.error(f"清理过期日志失败: {e}")


# 全局安全管理器实例
_security_manager = None


def get_security_manager() -> SecretVariableSecurity:
    """获取全局安全管理器实例"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecretVariableSecurity()
    return _security_manager 