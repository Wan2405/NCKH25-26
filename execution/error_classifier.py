"""
error_classifier.py (execution layer)

Mục đích:
    Re-export ErrorClassifier từ auto_grader/modules.
    Để các file trong execution/ có thể import trực tiếp.
"""

from auto_grader.modules.error_classifier import ErrorClassifier  # noqa: F401

__all__ = ["ErrorClassifier"]
