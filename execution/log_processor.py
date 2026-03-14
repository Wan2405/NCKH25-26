"""
LOG PROCESSOR (execution layer)
================================
Thin adapter around :class:`auto_grader.modules.log_processor.LogProcessor`
that accepts a raw log string rather than a file path.
"""

from __future__ import annotations

import logging
import os
import tempfile

from auto_grader.modules.log_processor import LogProcessor as _LogProcessor

logger = logging.getLogger(__name__)


class LogProcessor:
    """Parses a raw Maven/JUnit log string into a structured JSON-compatible dict."""

    def __init__(self, output_dir: str = "auto_grader/output/logs") -> None:
        self._inner = _LogProcessor(output_dir=output_dir)

    def process(self, raw_log: str, student_id: str, problem_id: str) -> dict:
        """
        Save *raw_log* to a temporary file, delegate to the underlying
        :class:`~auto_grader.modules.log_processor.LogProcessor`, and return
        the structured result dict.

        The JSON file is also persisted to *output_dir* by the inner processor.
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
                problem_id=problem_id,
            )
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
