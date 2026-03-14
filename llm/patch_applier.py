"""
PATCH APPLIER
=============
Applies unified-diff patches to Java source files.

Supports simple single-file unified diffs (the kind produced by
``diff -u`` or returned by LLMs).  ``--- / +++`` file headers are
ignored; only ``@@ … @@`` hunk markers and ``+`` / ``-`` / context
lines are processed.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def apply_patch(original: str, patch: str) -> str:
    """
    Apply a unified-diff *patch* to *original* and return the patched string.

    Falls back to returning *original* unchanged if the patch cannot be
    applied (e.g. context lines don't match or the patch is malformed).

    Args:
        original: Original source code as a string.
        patch:    Unified diff string (output of ``diff -u`` or similar).

    Returns:
        Patched source code, or *original* on failure.
    """
    try:
        return _apply(original, patch)
    except Exception as exc:
        logger.warning("Patch application failed (%s); returning original", exc)
        return original


def _apply(original: str, patch: str) -> str:
    lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    result: list[str] = list(lines)
    offset = 0

    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]

        # Skip file header lines (--- a/... +++ b/...)
        if line.startswith("---") or line.startswith("+++"):
            i += 1
            continue

        if line.startswith("@@"):
            # Parse: @@ -start[,count] +start[,count] @@
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not m:
                i += 1
                continue
            src_start = int(m.group(1)) - 1  # convert to 0-based index
            i += 1
            pos = src_start + offset

            while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
                pl = patch_lines[i]
                if pl.startswith("-"):
                    if pos < len(result):
                        result.pop(pos)
                        offset -= 1
                elif pl.startswith("+"):
                    result.insert(pos, pl[1:])
                    pos += 1
                    offset += 1
                else:
                    # Context line – advance position
                    pos += 1
                i += 1
            continue

        i += 1

    return "".join(result)
