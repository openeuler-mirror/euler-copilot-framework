import json
import base64
import hashlib
from typing import Any, Dict, List, Union, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .base import BaseVariable, VariableMetadata
from .type import VariableType


class StringVariable(BaseVariable):
    """字符串变量"""

    def _validate_type(self, value: Any) -> bool:
        """验证值是否为字符串类型"""
        return isinstance(value, str)

    def to_string(self) -> str:
        """转换为字符串"""
        return str(self._value) if self._value is not None else ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self._value,
            "scope": self.scope.value
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "StringVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        return cls(metadata, data["value"])


class NumberVariable(BaseVariable):
    """数字变量"""

    def _validate_type(self, value: Any) -> bool:
        """验证值是否为数字类型"""
        return isinstance(value, (int, float))

    def to_string(self) -> str:
        """转换为字符串"""
        return str(self._value) if self._value is not None else "0"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self._value,
            "scope": self.scope.value
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "NumberVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        return cls(metadata, data["value"])


class BooleanVariable(BaseVariable):
    """布尔变量"""

    def _validate_type(self, value: Any) -> bool:
        """验证值是否为布尔类型"""
        return isinstance(value, bool)

    def to_string(self) -> str:
        """转换为字符串"""
        return str(self._value).lower() if self._value is not None else "false"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self._value,
            "scope": self.scope.value
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "BooleanVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        return cls(metadata, data["value"])


class ObjectVariable(BaseVariable):
    """对象变量"""

    def _validate_type(self, value: Any) -> bool:
        """验证值是否为对象类型"""
        return isinstance(value, dict)

    def to_string(self) -> str:
        """转换为字符串"""
        if self._value is None:
            return "{}"
        try:
            return json.dumps(self._value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(self._value)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self._value,
            "scope": self.scope.value
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "ObjectVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        return cls(metadata, data["value"])


class SecretVariable(BaseVariable):
    """密钥变量 - 提供安全存储和访问机制"""

    def __init__(self, metadata: VariableMetadata, value: Any = None, encryption_key: Optional[str] = None):
        """初始化密钥变量

        Args:
            metadata: 变量元数据
            value: 变量值
            encryption_key: 加密密钥（可选，如果不提供会自动生成）
        """
        # 先设置加密密钥，因为父类初始化时可能会调用value setter
        self._encryption_key = encryption_key or self._generate_encryption_key()
        super().__init__(metadata, value)
        self.metadata.is_encrypted = True

        # 如果提供了值，确保它已被加密（在value setter中已处理）
        # 这里不需要再次加密，因为super().__init__已经通过setter处理了

    def _generate_encryption_key(self) -> str:
        """生成加密密钥"""
        # 使用用户ID和变量名生成唯一的加密密钥
        user_sub = self.metadata.user_sub or "default"
        salt = f"{user_sub}:{self.metadata.name}".encode()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(b"secret_variable_key"))
        return key.decode()

    def _encrypt_value(self, value: str) -> str:
        """加密值"""
        if not isinstance(value, str):
            value = str(value)

        f = Fernet(self._encryption_key.encode())
        encrypted_value = f.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted_value).decode()

    def _decrypt_value(self, encrypted_value: str) -> str:
        """解密值"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(
                encrypted_value.encode())
            f = Fernet(self._encryption_key.encode())
            decrypted_value = f.decrypt(encrypted_bytes)
            return decrypted_value.decode()
        except Exception:
            return "[解密失败]"

    def _validate_type(self, value: Any) -> bool:
        """验证值类型"""
        return isinstance(value, str)

    @property
    def value(self) -> str:
        """获取解密后的值"""
        if self._value is None:
            return ""
        return self._decrypt_value(self._value)

    @value.setter
    def value(self, new_value: Any) -> None:
        """设置新值（会自动加密）"""
        if self.scope.value == "system":
            raise ValueError("系统级变量不能修改")

        if not self._validate_type(new_value):
            raise TypeError(f"变量 {self.name} 的值类型不匹配，期望: {self.var_type}")

        self._value = self._encrypt_value(new_value)
        from datetime import datetime, UTC
        self.metadata.updated_at = datetime.now(UTC)

    def get_masked_value(self) -> str:
        """获取掩码值用于显示"""
        actual_value = self.value
        if len(actual_value) <= 4:
            return "*" * len(actual_value)
        return actual_value[:2] + "*" * (len(actual_value) - 4) + actual_value[-2:]

    def to_string(self) -> str:
        """转换为字符串（掩码形式）"""
        return self.get_masked_value()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（掩码形式）"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self.get_masked_value(),
            "scope": self.scope.value
        }

    def to_dict_with_actual_value(self, user_sub: str) -> Dict[str, Any]:
        """转换为包含实际值的字典（需要权限检查）"""
        if not self.can_access(user_sub):
            raise PermissionError(f"用户 {user_sub} 没有权限访问密钥变量 {self.name}")

        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self.value,  # 实际解密值
            "scope": self.scope.value
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化（保持加密状态）"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,  # 加密后的值
            "encryption_key": self._encryption_key,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "SecretVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        instance = cls(metadata, None, data.get("encryption_key"))
        instance._value = data["value"]  # 直接设置加密值
        return instance


class FileVariable(BaseVariable):
    """文件变量"""

    def _validate_type(self, value: Any) -> bool:
        """验证值是否为文件路径或文件配置对象"""
        # 支持字符串类型（文件路径或文件ID）
        if isinstance(value, str):
            return True

        # 支持字典类型
        if isinstance(value, dict):
            # 旧格式：包含filename和content的文件对象
            if "filename" in value and "content" in value:
                return True

            # 新格式：包含file_id的文件配置对象
            if "file_id" in value:
                return True

            # 支持其他文件相关的字典结构
            return True

        return False

    def to_string(self) -> str:
        """转换为字符串"""
        if isinstance(self._value, str):
            return self._value
        elif isinstance(self._value, dict):
            return self._value.get("filename", "unnamed_file")
        return ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self._value,
            "scope": self.scope.value
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "FileVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        return cls(metadata, data["value"])


class ArrayVariable(BaseVariable):
    """数组变量"""

    def __init__(self, metadata: VariableMetadata, value: Any = None):
        """初始化数组变量"""
        # 先设置元素类型，因为父类初始化时会调用_validate_type
        self._element_type = metadata.var_type.get_array_element_type()
        super().__init__(metadata, value or [])

    def _validate_type(self, value: Any) -> bool:
        """验证值是否为数组类型，并检查元素类型"""
        # 特殊处理：对于ARRAY_FILE类型，支持字典配置格式
        if (hasattr(self, '_element_type') and
            self._element_type == VariableType.FILE and
            isinstance(value, dict) and
                "file_ids" in value):
            # 这是ARRAY_FILE类型的配置字典，直接接受
            return True

        if not isinstance(value, list):
            return False

        # 如果是 array[any]，不需要检查元素类型
        if self._element_type is None:
            return True

        # 检查所有元素类型
        for item in value:
            if not self._validate_element_type(item):
                return False

        return True

    def _validate_element_type(self, element: Any) -> bool:
        """验证单个元素的类型"""
        if self._element_type is None:  # array[any]
            return True

        type_validators = {
            VariableType.STRING: lambda x: isinstance(x, str),
            VariableType.NUMBER: lambda x: isinstance(x, (int, float)),
            VariableType.BOOLEAN: lambda x: isinstance(x, bool),
            VariableType.OBJECT: lambda x: isinstance(x, dict),
            VariableType.SECRET: lambda x: isinstance(x, str),
            VariableType.FILE: lambda x: isinstance(x, (str, dict)),
        }

        validator = type_validators.get(self._element_type)
        return validator(element) if validator else False

    def append(self, item: Any) -> None:
        """添加元素到数组"""
        if not self._validate_element_type(item):
            raise TypeError(f"元素类型不匹配，期望: {self._element_type}")

        # 特殊处理ARRAY_FILE类型的字典格式
        if (hasattr(self, '_element_type') and
            self._element_type == VariableType.FILE and
            isinstance(self._value, dict) and
                "file_ids" in self._value):
            self._value["file_ids"].append(item)
            from datetime import datetime, UTC
            self.metadata.updated_at = datetime.now(UTC)
            return

        if self._value is None:
            self._value = []
        self._value.append(item)
        from datetime import datetime, UTC
        self.metadata.updated_at = datetime.now(UTC)

    def remove(self, item: Any) -> None:
        """从数组中移除元素"""
        # 特殊处理ARRAY_FILE类型的字典格式
        if (hasattr(self, '_element_type') and
            self._element_type == VariableType.FILE and
            isinstance(self._value, dict) and
                "file_ids" in self._value):
            if item in self._value["file_ids"]:
                self._value["file_ids"].remove(item)
                from datetime import datetime, UTC
                self.metadata.updated_at = datetime.now(UTC)
            return

        if self._value and item in self._value:
            self._value.remove(item)
            from datetime import datetime, UTC
            self.metadata.updated_at = datetime.now(UTC)

    def __len__(self) -> int:
        """获取数组长度"""
        # 特殊处理ARRAY_FILE类型的字典格式
        if (hasattr(self, '_element_type') and
            self._element_type == VariableType.FILE and
            isinstance(self._value, dict) and
                "file_ids" in self._value):
            return len(self._value["file_ids"])

        return len(self._value) if self._value else 0

    def __getitem__(self, index: int) -> Any:
        """获取指定索引的元素"""
        # 特殊处理ARRAY_FILE类型的字典格式
        if (hasattr(self, '_element_type') and
            self._element_type == VariableType.FILE and
            isinstance(self._value, dict) and
                "file_ids" in self._value):
            return self._value["file_ids"][index]

        if self._value is None:
            raise IndexError("数组为空")
        return self._value[index]

    def __setitem__(self, index: int, value: Any) -> None:
        """设置指定索引的元素"""
        # 特殊处理ARRAY_FILE类型的字典格式
        if (hasattr(self, '_element_type') and
            self._element_type == VariableType.FILE and
            isinstance(self._value, dict) and
                "file_ids" in self._value):
            self._value["file_ids"][index] = value
            from datetime import datetime, UTC
            self.metadata.updated_at = datetime.now(UTC)
            return

        if not self._validate_element_type(value):
            raise TypeError(f"元素类型不匹配，期望: {self._element_type}")

        if self._value is None:
            self._value = []
        self._value[index] = value
        from datetime import datetime, UTC
        self.metadata.updated_at = datetime.now(UTC)

    def to_string(self) -> str:
        """转换为字符串"""
        if self._value is None:
            return "[]"
        try:
            return json.dumps(self._value, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(self._value)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": self._value,
            "scope": self.scope.value,
            "element_type": self._element_type.value if self._element_type else None
        }

    def serialize(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "metadata": self.metadata.model_dump(),
            "value": self._value,
            "class": self.__class__.__name__
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "ArrayVariable":
        """反序列化"""
        metadata = VariableMetadata(**data["metadata"])
        return cls(metadata, data["value"])


# 变量类型映射
VARIABLE_CLASS_MAP = {
    VariableType.STRING: StringVariable,
    VariableType.NUMBER: NumberVariable,
    VariableType.BOOLEAN: BooleanVariable,
    VariableType.OBJECT: ObjectVariable,
    VariableType.SECRET: SecretVariable,
    VariableType.FILE: FileVariable,
    VariableType.ARRAY: ArrayVariable,
    VariableType.ARRAY_ANY: ArrayVariable,
    VariableType.ARRAY_STRING: ArrayVariable,
    VariableType.ARRAY_NUMBER: ArrayVariable,
    VariableType.ARRAY_OBJECT: ArrayVariable,
    VariableType.ARRAY_FILE: ArrayVariable,
    VariableType.ARRAY_BOOLEAN: ArrayVariable,
    VariableType.ARRAY_SECRET: ArrayVariable,
}


def create_variable(metadata: VariableMetadata, value: Any = None) -> BaseVariable:
    """根据类型创建变量实例

    Args:
        metadata: 变量元数据
        value: 变量值

    Returns:
        BaseVariable: 创建的变量实例
    """
    variable_class = VARIABLE_CLASS_MAP.get(metadata.var_type)
    if not variable_class:
        raise ValueError(f"不支持的变量类型: {metadata.var_type}")

    return variable_class(metadata, value)
