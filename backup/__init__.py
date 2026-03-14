"""
Package chứa các module xử lý cho Auto Grader
"""

from .log_processor import LogProcessor
from .error_classifier import ErrorClassifier

__all__ = ['LogProcessor', 'ErrorClassifier']