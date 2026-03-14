"""
ERROR CLASSIFIER (execution layer)
====================================
Re-exports :class:`auto_grader.modules.error_classifier.ErrorClassifier`
so that code in the top-level packages can import directly from
``execution``.
"""

from auto_grader.modules.error_classifier import ErrorClassifier  # noqa: F401

__all__ = ["ErrorClassifier"]
