import logging
import os
import shutil
from enum import Enum
from typing import Dict, List, Optional
from pydantic import Field
from config.public.base_config_loader import BaseConfig, LanguageEnum

# 初始化日志
logger = logging.getLogger("file_tool")
logger.setLevel(logging.INFO)
lang = BaseConfig().get_config().public_config.language
# ========== 枚举类定义（提升大模型识别性） ==========
class FileActionEnum(str, Enum):
    """文件操作类型枚举"""
    LS = "ls"          # 查看文件/目录
    CAT = "cat"        # 读取文件内容
    ADD = "add"        # 新建空文件
    APPEND = "append"  # 追加内容
    EDIT = "edit"      # 覆盖内容
    RENAME = "rename"  # 重命名
    CHMOD = "chmod"    # 修改权限
    DELETE = "delete"  # 删除文件/目录

class FileEncodingEnum(str, Enum):
    """文件编码枚举"""
    UTF8 = "utf-8"
    GBK = "gbk"
    GB2312 = "gb2312"
    ASCII = "ascii"

class CacheTypeEnum(str, Enum):
    """缓存类型枚举（预留扩展）"""
    ALL = "all"
    PACKAGES = "packages"
    METADATA = "metadata"

# ========== 通用工具函数 ==========
def get_language() -> bool:
    """获取语言配置：True=中文，False=英文"""
    return BaseConfig().get_config().public_config.language == LanguageEnum.ZH

def init_result_dict(
        target_host: str = "127.0.0.1",
        result_type: str = "list",
        include_file_path: bool = True
) -> Dict:
    """初始化返回结果字典（默认包含file_path字段）"""
    result = {
        "success": False,
        "message": "",
        "result": [] if result_type == "list" else "",
        "target": target_host,
        "file_path": ""
    }
    return result

# ========== 文件管理核心类 ==========
class FileManager:
    """文件管理核心类（Python原生实现，无shell依赖）"""
    def __init__(self, lang: LanguageEnum = LanguageEnum.ZH):
        self.is_zh = lang

    def _get_error_msg(self, zh_msg: str, en_msg: str) -> str:
        """多语言错误提示"""
        return zh_msg if self.is_zh else en_msg

    def ls(self, file_path: str, detail: bool = Field(False, description="是否显示详细信息")) -> List[Dict]:
        """
        查看文件/目录状态（Python实现ls功能）
        :param file_path: 文件/目录路径（必填）
        :param detail: 是否显示详细信息（默认False）
        :return: 结构化文件信息列表
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(self._get_error_msg(f"路径不存在：{file_path}", f"Path not found: {file_path}"))

        result = []
        if os.path.isfile(file_path):
            # 单个文件
            stat = os.stat(file_path)
            file_info = {
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "mode": oct(stat.st_mode)[-3:],
                "type": "file"
            }
            result.append(file_info)
        else:
            # 目录
            for item in os.listdir(file_path):
                full_path = os.path.join(file_path, item)
                stat = os.stat(full_path)
                item_info = {
                    "name": item,
                    "path": full_path,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "mode": oct(stat.st_mode)[-3:],
                    "type": "file" if os.path.isfile(full_path) else "dir"
                }
                result.append(item_info)
        return result

    def cat(self,
            file_path: str,
            encoding: FileEncodingEnum = Field(FileEncodingEnum.UTF8, description="文件编码")) -> List[str]:
        """
        读取文件内容（Python实现cat功能）
        :param file_path: 文件路径（必填）
        :param encoding: 文件编码（默认utf-8）
        :return: 按行拆分的内容列表
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(self._get_error_msg(f"文件不存在：{file_path}", f"File not found: {file_path}"))
        if os.path.isdir(file_path):
            raise IsADirectoryError(self._get_error_msg(f"路径是目录，无法读取内容：{file_path}", f"Path is directory, cannot read content: {file_path}"))

        with open(file_path, "r", encoding=encoding.value, errors="ignore") as f:
            content = [line.rstrip("\n") for line in f.readlines()]
        return content

    def add(self,
            file_path: str,
            overwrite: bool = Field(False, description="是否覆盖已存在文件"),
            content: Optional[str] = Field(None, description="创建文件时写入的内容，为None则创建空文件"),
            encoding: str = Field(FileEncodingEnum.UTF8.value, description="文件编码")
            ) -> None:
        """
        新建文件（支持创建空文件或写入指定内容，Python实现touch功能）
        :param file_path: 文件路径（必填，绝对路径）
        :param overwrite: 已存在时是否覆盖（默认False）
        :param content: 创建文件时写入的内容，为None则创建空文件（新增参数）
        :param encoding: 文件编码（默认utf-8，新增参数用于内容写入）
        """
        # 1. 检查文件是否存在，且不允许覆盖则跳过
        if os.path.exists(file_path) and not overwrite:
            logger.info(self._get_error_msg(f"文件已存在，跳过创建：{file_path}", f"File exists, skip creation: {file_path}"))
            return

        # 2. 确保父目录存在
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        # 3. 根据content参数决定写入内容还是创建空文件
        with open(file_path, "w", encoding=encoding) as f:
            if content is not None:
                f.write(content)  # 写入指定内容
            # content为None时，仅打开文件后关闭（创建空文件）

        # 4. 日志提示（区分空文件和带内容文件）
        if content is None:
            logger.info(self._get_error_msg(f"空文件创建成功：{file_path}", f"Empty file created successfully: {file_path}"))
        else:
            logger.info(self._get_error_msg(f"文件创建并写入内容成功：{file_path}", f"File created and content written successfully: {file_path}"))

    def append(self,
               file_path: str,
               content: str = Field(..., description="追加内容"),
               encoding: FileEncodingEnum = Field(FileEncodingEnum.UTF8, description="文件编码")) -> None:
        """
        追加内容到文件
        :param file_path: 文件路径（必填）
        :param content: 追加内容（必填）
        :param encoding: 文件编码（默认utf-8）
        """
        if not content:
            raise ValueError(self._get_error_msg("追加内容不能为空", "Append content cannot be empty"))

        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(file_path, "a", encoding=encoding.value) as f:
            f.write(content + "\n")
        logger.info(self._get_error_msg(f"内容追加成功：{file_path}", f"Content appended successfully: {file_path}"))

    def edit(self,
             file_path: str,
             content: str = Field(..., description="覆盖内容"),
             encoding: FileEncodingEnum = Field(FileEncodingEnum.UTF8, description="文件编码")) -> None:
        """
        覆盖写入文件内容
        :param file_path: 文件路径（必填）
        :param content: 覆盖内容（必填）
        :param encoding: 文件编码（默认utf-8）
        """
        if not content:
            raise ValueError(self._get_error_msg("覆盖内容不能为空", "Edit content cannot be empty"))

        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(file_path, "w", encoding=encoding.value) as f:
            f.write(content)
        logger.info(self._get_error_msg(f"文件内容覆盖成功：{file_path}", f"File content overwritten successfully: {file_path}"))

    def rename(self,
               old_path: str,
               new_path: str = Field(..., description="新路径")) -> None:
        """
        重命名文件/目录
        :param old_path: 原路径（必填）
        :param new_path: 新路径（必填）
        """
        if not os.path.exists(old_path):
            raise FileNotFoundError(self._get_error_msg(f"原路径不存在：{old_path}", f"Old path not found: {old_path}"))
        if os.path.exists(new_path):
            raise FileExistsError(self._get_error_msg(f"新路径已存在：{new_path}", f"New path already exists: {new_path}"))

        shutil.move(old_path, new_path)
        logger.info(self._get_error_msg(f"文件重命名成功：{old_path} → {new_path}", f"File renamed successfully: {old_path} → {new_path}"))

    def chmod(self,
              file_path: str,
              mode: str = Field(..., description="权限模式（如755）")) -> None:
        """
        修改文件权限
        :param file_path: 文件路径（必填）
        :param mode: 权限模式（必填，如755）
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(self._get_error_msg(f"文件不存在：{file_path}", f"File not found: {file_path}"))

        try:
            numeric_mode = int(mode, 8)
            os.chmod(file_path, numeric_mode)
            logger.info(self._get_error_msg(f"权限修改成功：{file_path} → {mode}", f"Permission modified successfully: {file_path} → {mode}"))
        except ValueError:
            raise ValueError(self._get_error_msg(f"权限格式错误（需为8进制，如755）：{mode}", f"Invalid mode format (must be octal, e.g.755): {mode}"))

    def delete(self,
               file_path: str,
               recursive: bool = Field(False, description="是否递归删除目录")) -> None:
        """
        删除文件/目录
        :param file_path: 文件/目录路径（必填）
        :param recursive: 是否递归删除目录（默认False）
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(self._get_error_msg(f"路径不存在：{file_path}", f"Path not found: {file_path}"))

        if os.path.isfile(file_path):
            os.remove(file_path)
        else:
            if not recursive:
                raise IsADirectoryError(self._get_error_msg(f"路径是目录，需开启recursive=True递归删除：{file_path}", f"Path is directory, set recursive=True to delete: {file_path}"))
            shutil.rmtree(file_path)
        logger.info(self._get_error_msg(f"路径删除成功：{file_path}", f"Path deleted successfully: {file_path}"))