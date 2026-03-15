"""
executor.py

Mục đích:
    Cung cấp hàm extract_class_name để lấy tên class từ code Java.

Lưu ý:
    Việc compile và chạy code PHẢI qua Docker (DockerManager),
    KHÔNG chạy trực tiếp trên máy host.
"""

import logging
import re

logger = logging.getLogger(__name__)


def extract_class_name(code: str) -> str:
    """
    Trích xuất tên class từ code Java.
    
    Ưu tiên tìm public class, nếu không có thì lấy class đầu tiên.
    Nếu không tìm được class nào, trả về "Solution".
    """
    match = re.search(r"public\s+class\s+(\w+)", code)
    if match:
        return match.group(1)
    match = re.search(r"class\s+(\w+)", code)
    if match:
        return match.group(1)
    return "Solution"
