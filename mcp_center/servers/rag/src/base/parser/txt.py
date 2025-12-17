import chardet
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def detect_encoding(file_path: str) -> str:
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        if encoding is None:
            encoding = 'utf-8'
        return encoding
    except Exception as e:
        logger.exception(f"[TxtParser] 检测编码失败: {e}")
        return 'utf-8'


def parse_txt(file_path: str) -> Optional[str]:
    try:
        encoding = detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding, errors='ignore') as file:
            content = file.read()
        return content
    except Exception as e:
        logger.exception(f"[TxtParser] 解析TXT文件失败: {e}")
        return None

