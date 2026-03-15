"""
code_sanitizer.py

Mục đích:
    Làm sạch code Java mà LLM trả về trước khi compile.
    
Tại sao cần:
    LLM thường trả về code với nhiều "rác":
    - Markdown code fences (```java ... ```)
    - Câu giới thiệu kiểu "Here is the fixed code:"
    - Đổi tên class (khiến javac báo lỗi vì tên file không khớp)
    - Thêm class test không cần thiết

Cách hoạt động:
    1. Bỏ markdown fences
    2. Bỏ phần text mở đầu
    3. Chỉ giữ class đầu tiên
    4. Sửa lại tên class nếu cần
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Regex để tìm markdown code fence
_FENCE_RE = re.compile(r"`{3}(?:java|Java)?\s*\n?(.*?)`{3}", re.DOTALL)

# Regex để tìm khai báo public class
_CLASS_DECL_RE = re.compile(r"(public\s+class\s+)\w+")


# === Các hàm làm sạch code ===


def strip_markdown_fences(code: str) -> str:
    """Bỏ markdown code fence (```java ... ```) nếu có."""
    m = _FENCE_RE.search(code)
    if m:
        return m.group(1).strip("\n")
    return code


def strip_preamble(code: str) -> str:
    """
    Bỏ phần text mở đầu trước code Java thật.
    
    LLM hay thêm câu kiểu "Here is the corrected version:".
    Hàm này tìm dòng đầu tiên giống Java (package, import, public, //)
    và bỏ tất cả text phía trước.
    """
    java_starters = re.compile(
        r"^\s*(package |import |public |//|/\*|class )", re.MULTILINE
    )
    m = java_starters.search(code)
    if m and m.start() > 0:
        return code[m.start():]
    return code


def enforce_class_name(code: str, expected_class: str) -> str:
    """
    Sửa tên class để khớp với tên file.
    
    Trong Java, tên public class phải trùng tên file.
    LLM đôi khi đổi tên class, hàm này sửa lại.
    """
    if not expected_class:
        return code
    return _CLASS_DECL_RE.sub(r"\g<1>" + expected_class, code, count=1)


def keep_only_first_class(code: str, expected_class: str | None = None) -> str:
    """
    Chỉ giữ class đầu tiên, bỏ các class khác.
    
    LLM đôi khi thêm class test hoặc class phụ.
    Hàm này tìm class đầu tiên và bỏ mọi thứ sau nó.
    
    Cách hoạt động:
        1. Tìm khai báo class đầu tiên
        2. Đếm cặp {} để xác định vị trí kết thúc class
        3. Cắt bỏ phần code sau class đó
    """
    # Tìm khai báo class đầu tiên (có hoặc không có 'public')
    class_pattern = r"(?:public\s+)?class\s+(\w+)"
    match = re.search(class_pattern, code)
    
    if not match:
        return code
    
    class_start = match.start()
    class_name = match.group(1)
    
    # Nếu có expected_class, kiểm tra xem có khớp không
    if expected_class and class_name != expected_class:
        logger.warning(
            f"Expected class name '{expected_class}' but found '{class_name}'"
        )
    
    # Tìm dấu { mở đầu của class
    open_brace_pos = code.find("{", class_start)
    if open_brace_pos == -1:
        return code
    
    # Đếm cặp {} để tìm dấu } đóng class
    # Phải cẩn thận với { } trong string và comment
    brace_count = 0
    last_close_brace = -1
    in_string = False
    in_char = False
    
    i = open_brace_pos
    while i < len(code):
        # Bỏ qua comment dạng //
        if not in_string and not in_char and code[i:i+2] == "//":
            i = code.find("\n", i)
            if i == -1: break
            continue
            
        # Bỏ qua comment dạng /* ... */
        if not in_string and not in_char and code[i:i+2] == "/*":
            i = code.find("*/", i + 2)
            if i == -1: break
            i += 2
            continue
            
        char = code[i]
        
        # Xử lý string và char literal để không đếm {} bên trong
        if char == '"' and (i == 0 or code[i-1] != '\\') and not in_char:
            in_string = not in_string
        elif char == "'" and (i == 0 or code[i-1] != '\\') and not in_string:
            in_char = not in_char
            
        # Chỉ đếm {} khi không nằm trong string/char
        if not in_string and not in_char:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    last_close_brace = i
                    break
        i += 1
    
    if last_close_brace == -1:
        return code
    
    # Lấy phần code từ đầu class đến hết class
    first_class_code = code[class_start:last_close_brace + 1]
    
    # Lấy phần đầu (package, imports...)
    preamble = code[:class_start]
    
    return preamble + first_class_code


def sanitize_java_code(code: str, expected_class: str | None = None) -> str:
    """
    Hàm chính để làm sạch code Java từ LLM.
    
    Các bước xử lý:
        1. Bỏ markdown fence
        2. Bỏ text mở đầu
        3. Chỉ giữ class đầu tiên
        4. Bỏ khoảng trắng thừa
        5. Sửa tên class nếu cần
    
    Tham số:
        code: Code thô từ LLM
        expected_class: Tên class mong muốn (vd: "Solution")
    
    Trả về:
        Code Java đã làm sạch, sẵn sàng compile.
    """
    if not code or not code.strip():
        return code

    cleaned = strip_markdown_fences(code)
    cleaned = strip_preamble(cleaned)
    cleaned = keep_only_first_class(cleaned, expected_class)
    cleaned = cleaned.strip()

    if expected_class:
        cleaned = enforce_class_name(cleaned, expected_class)

    # Kiểm tra xem kết quả có phải Java code không
    # Nếu không có từ khóa 'class' thì trả về code gốc
    if not re.search(r'\bclass\s+', cleaned):
        logger.warning(
            "Sanitized code does not contain a 'class' keyword – "
            "returning original code to avoid data loss."
        )
        return code

    return cleaned