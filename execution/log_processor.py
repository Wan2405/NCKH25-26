"""
log_processor.py (execution layer)

Mục đích:
    Adapter để dùng LogProcessor từ auto_grader/modules.
    Nhận log dạng string thay vì đường dẫn file.
    
Cách hoạt động:
    1. Lưu log string vào file tạm
    2. Gọi LogProcessor gốc xử lý file đó
    3. Xóa file tạm và trả về kết quả
"""

from __future__ import annotations

import logging
import os
import tempfile

from auto_grader.modules.log_processor import LogProcessor as _LogProcessor

logger = logging.getLogger(__name__)


class LogProcessor:
    """Phân tích log Maven/JUnit thành dict chuẩn hóa."""

    def __init__(self, output_dir: str = "auto_grader/output/logs") -> None:
        self._inner = _LogProcessor(output_dir=output_dir)

    def process(self, raw_log: str, student_id: str = "SV001") -> dict:
        """
        Xử lý log string và trả về dict chứa thông tin lỗi.
        
        Tham số:
            raw_log: Nội dung log dạng string
            student_id: ID sinh viên (để đặt tên file output)
        
        Trả về:
            Dict chứa metadata, loại lỗi, chi tiết test, v.v.
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(raw_log)
            tmp_path = tmp.name

        try:
            result = self._inner.process_log(
                log_path=tmp_path,
                student_id=student_id,
            )
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
