# src/converter.py
from io import BytesIO
from markitdown import MarkItDown
import logging

logger = logging.getLogger("davybase.converter")

class Converter:
    """格式转换器"""

    def __init__(self, data_dir: str):
        self.md = MarkItDown()

    def convert(self, content: str, note_type: str) -> str:
        """转换内容

        Args:
            content: 原始内容
            note_type: 笔记类型

        Returns:
            转换后的 Markdown
        """
        if note_type in ("plain_text", "img_text"):
            return content

        if note_type == "link":
            return self.convert_html(content)

        if note_type in ("audio", "meeting", "local_audio", "internal_record"):
            return content

        return content

    def convert_html(self, html: str) -> str:
        """HTML 转 Markdown"""
        try:
            result = self.md.convert_stream(BytesIO(html.encode('utf-8')))
            return result.text_content
        except Exception as e:
            logger.warning(f"HTML 转换失败：{e}")
            return html
