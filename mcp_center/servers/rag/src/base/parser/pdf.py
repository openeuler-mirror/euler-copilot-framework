"""
PDF 文件解析器
使用 PyMuPDF (fitz) 提取 PDF 中的文本内容
"""
import logging
from typing import Optional
import fitz

logger = logging.getLogger(__name__)


def parse_pdf(file_path: str) -> Optional[str]:
    """
    解析 PDF 文件，提取文本内容
    
    :param file_path: PDF 文件路径
    :return: 提取的文本内容，如果失败则返回 None
    """
    try:
        # 打开 PDF 文件
        pdf_doc = fitz.open(file_path)
        
        if not pdf_doc:
            logger.error("[PdfParser] 无法打开 PDF 文件")
            return None
        
        text_blocks = []
        
        # 遍历每一页
        for page_num in range(len(pdf_doc)):
            page = pdf_doc.load_page(page_num)
            
            # 获取文本块
            blocks = page.get_text("blocks")
            
            # 提取文本块内容
            for block in blocks:
                if block[6] == 0:  # 确保是文本块（block[6] == 0 表示文本块）
                    text = block[4].strip()  # block[4] 是文本内容
                    if text:
                        # 保存文本和位置信息用于排序
                        bbox = block[:4]  # (x0, y0, x1, y1)
                        text_blocks.append({
                            'text': text,
                            'y0': bbox[1],  # 上边界，用于排序
                            'x0': bbox[0]   # 左边界，用于排序
                        })
        
        # 关闭 PDF 文档
        pdf_doc.close()
        
        if not text_blocks:
            logger.warning("[PdfParser] PDF 文件中没有找到文本内容")
            return None
        
        # 按位置排序（从上到下，从左到右）
        text_blocks.sort(key=lambda x: (x['y0'], x['x0']))
        
        # 合并文本块，添加换行
        paragraphs = []
        prev_y0 = None
        
        for block in text_blocks:
            text = block['text']
            y0 = block['y0']
            
            # 如果当前块与上一个块在垂直方向上有较大距离，添加换行
            if prev_y0 is not None and y0 - prev_y0 > 10:  # 10 像素的阈值，表示新段落
                paragraphs.append('')
            
            paragraphs.append(text)
            prev_y0 = y0
        
        content = '\n'.join(paragraphs)
        return content
        
    except Exception as e:
        logger.exception(f"[PdfParser] 解析 PDF 文件失败: {e}")
        return None

