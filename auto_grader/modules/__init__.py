"""
Package auto_grader/modules - Các module xử lý chính của hệ thống chấm bài.

Bao gồm:
    - executor: Hàm trích xuất tên class từ code Java
    - LogProcessor: Xử lý log Maven/JUnit
    - ErrorClassifier: Phân loại lỗi (compile, runtime, test failed)
    - FeedbackGenerator: Tạo gợi ý sửa lỗi từ LLM
    - CodeGenerator: Sinh code Java từ đề bài
    - AutoFixer: Vòng lặp tự động sửa code
"""

from .executor import extract_class_name
from .log_processor import LogProcessor
from .error_classifier import ErrorClassifier
from .feedback_generator import FeedbackGenerator
from .code_generator import CodeGenerator
from .auto_fixer import AutoFixer

__all__ = [
    "extract_class_name",
    "LogProcessor",
    "ErrorClassifier",
    "FeedbackGenerator",
    "CodeGenerator",
    "AutoFixer",
]
