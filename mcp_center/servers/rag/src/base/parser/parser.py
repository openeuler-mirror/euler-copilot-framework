"""
文档解析器模块
"""
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

from base.parser.txt import parse_txt
from base.parser.doc import parse_docx, parse_doc
from base.parser.pdf import parse_pdf



_parsers: Dict[str, callable] = {}


def register_parser(file_ext: str, parser_func: callable):
    """
    注册解析器
    :param file_ext: 文件扩展名（如 'txt', 'docx'）
    :param parser_func: 解析函数，接收 file_path 参数，返回 Optional[str]
    """
    _parsers[file_ext.lower()] = parser_func
    logger.debug(f"[Parser] 注册解析器: {file_ext}")


def parse(file_path: str) -> Optional[str]:
    """
    根据文件类型自动选择解析器
    :param file_path: 文件路径
    :return: 文件内容
    """
    file_ext = file_path.lower().split('.')[-1]
    if file_ext == "md":
        file_ext = "txt"
    if file_ext not in _parsers:
        logger.error(f"[Parser] 不支持的文件类型: {file_ext}")
        return None

    try:
        parser_func = _parsers[file_ext]
        return parser_func(file_path)
    except Exception as e:
        logger.exception(f"[Parser] 解析文件失败: {file_path}, {e}")
        return None


# 注册解析器
register_parser('txt', parse_txt)
register_parser('docx', parse_docx)
register_parser('doc', parse_doc)
register_parser('pdf', parse_pdf)


class Parser:
    """文档解析器类"""

    @staticmethod
    def parse(file_path: str) -> Optional[str]:
        return parse(file_path)
