from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime, UTC

from .type import VariableType, VariableScope


class VariableMetadata(BaseModel):
    """变量元数据"""
    name: str = Field(description="变量名称")
    var_type: VariableType = Field(description="变量类型")
    scope: VariableScope = Field(description="变量作用域")
    description: Optional[str] = Field(default=None, description="变量描述")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="更新时间")
    created_by: Optional[str] = Field(default=None, description="创建者用户ID")
    
    # 作用域相关属性
    user_sub: Optional[str] = Field(default=None, description="用户级变量的用户ID")
    flow_id: Optional[str] = Field(default=None, description="环境级/对话级变量的流程ID")
    
    # 安全相关属性
    is_encrypted: bool = Field(default=False, description="是否加密存储")
    access_permissions: Optional[Dict[str, Any]] = Field(default=None, description="访问权限")


class BaseVariable(ABC):
    """变量处理基类"""
    
    def __init__(self, metadata: VariableMetadata, value: Any = None):
        """初始化变量
        
        Args:
            metadata: 变量元数据
            value: 变量值
        """
        self.metadata = metadata
        self._value = None  # 先设置为None
        self._original_value = value
        self._initializing = True  # 标记正在初始化
        
        # 通过setter设置值，触发类型验证
        if value is not None:
            self.value = value  # 这会触发setter和类型验证
        else:
            self._value = value  # 如果是None则直接设置
            
        self._initializing = False  # 初始化完成
    
    @property
    def name(self) -> str:
        """获取变量名称"""
        return self.metadata.name
    
    @property
    def var_type(self) -> VariableType:
        """获取变量类型"""
        return self.metadata.var_type
    
    @property
    def scope(self) -> VariableScope:
        """获取变量作用域"""
        return self.metadata.scope
    
    @property
    def value(self) -> Any:
        """获取变量值"""
        return self._value
    
    @value.setter
    def value(self, new_value: Any) -> None:
        """设置变量值"""
        # 只有在非初始化阶段才检查系统级变量的修改限制
        if self.scope == VariableScope.SYSTEM and not getattr(self, '_initializing', False):
            raise ValueError("系统级变量不能修改")
        
        # 验证类型
        if not self._validate_type(new_value):
            raise TypeError(f"变量 {self.name} 的值类型不匹配，期望: {self.var_type}")
        
        self._value = new_value
        self.metadata.updated_at = datetime.now(UTC)
    
    @abstractmethod
    def _validate_type(self, value: Any) -> bool:
        """验证值的类型是否正确
        
        Args:
            value: 要验证的值
            
        Returns:
            bool: 类型是否正确
        """
        pass
    
    @abstractmethod
    def to_string(self) -> str:
        """将变量转换为字符串表示
        
        Returns:
            str: 字符串表示
        """
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """将变量转换为字典表示
        
        Returns:
            Dict[str, Any]: 字典表示
        """
        pass
    
    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """序列化变量用于存储
        
        Returns:
            Dict[str, Any]: 序列化后的数据
        """
        pass
    
    @classmethod
    @abstractmethod
    def deserialize(cls, data: Dict[str, Any]) -> "BaseVariable":
        """从序列化数据恢复变量
        
        Args:
            data: 序列化数据
            
        Returns:
            BaseVariable: 恢复的变量实例
        """
        pass
    
    def copy(self) -> "BaseVariable":
        """创建变量的副本
        
        Returns:
            BaseVariable: 变量副本
        """
        # 深拷贝元数据和值
        import copy
        new_metadata = copy.deepcopy(self.metadata)
        new_value = copy.deepcopy(self._value)
        return self.__class__(new_metadata, new_value)
    
    def reset(self) -> None:
        """重置变量到初始值"""
        if self.scope == VariableScope.SYSTEM:
            raise ValueError("系统级变量不能重置")
        
        self._value = self._original_value
        self.metadata.updated_at = datetime.now(UTC)
    
    def can_access(self, user_sub: str) -> bool:
        """检查用户是否有权限访问此变量
        
        Args:
            user_sub: 用户ID
            
        Returns:
            bool: 是否有权限访问
        """
        # 系统级变量所有人都可以访问
        if self.scope == VariableScope.SYSTEM:
            return True
        
        # 用户级变量只有创建者可以访问
        if self.scope == VariableScope.USER:
            return self.metadata.user_sub == user_sub
        
        # 环境级和对话级变量根据上下文判断（这里简化处理）
        return True
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.name}({self.var_type.value})={self.to_string()}"
    
    def __repr__(self) -> str:
        """调试表示"""
        return f"<{self.__class__.__name__}(name='{self.name}', type='{self.var_type.value}', scope='{self.scope.value}')>" 