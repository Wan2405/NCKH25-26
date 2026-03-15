"""
patch_applier.py

Mục đích:
    Áp dụng unified diff patch vào code gốc.
    Dùng khi LLM trả về dạng patch thay vì code đầy đủ.

Cách hoạt động:
    1. Parse các hunk header (@@ -start,count +start,count @@)
    2. Với mỗi dòng có prefix:
       - "-" : xóa dòng này
       - "+" : thêm dòng này
       - " " : giữ nguyên (context)
    3. Trả về code đã áp dụng patch

Lưu ý:
    Nếu patch không áp dụng được (context không khớp),
    hàm trả về code gốc không thay đổi.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def apply_patch(original: str, patch: str) -> str:
    """
    Áp dụng patch vào code gốc.
    
    Tham số:
        original: Code gốc
        patch: Nội dung patch dạng unified diff
    
    Trả về:
        Code đã patch, hoặc code gốc nếu patch thất bại.
    """
    try:
        return _apply(original, patch)
    except Exception as exc:
        logger.warning("Patch application failed (%s); returning original", exc)
        return original


def _apply(original: str, patch: str) -> str:
    """Hàm nội bộ thực hiện áp dụng patch."""
    lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    result: list[str] = list(lines)
    offset = 0  # Lưu offset khi thêm/xóa dòng

    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]

        # Bỏ qua header dòng --- và +++
        if line.startswith("---") or line.startswith("+++"):
            i += 1
            continue

        if line.startswith("@@"):
            # Parse hunk header: @@ -start[,count] +start[,count] @@
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if not m:
                i += 1
                continue
            src_start = int(m.group(1)) - 1  # Chuyển về 0-based index
            i += 1
            pos = src_start + offset

            # Xử lý các dòng trong hunk
            while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
                pl = patch_lines[i]
                if pl.startswith("-"):
                    # Xóa dòng
                    if pos < len(result):
                        result.pop(pos)
                        offset -= 1
                elif pl.startswith("+"):
                    # Thêm dòng mới
                    result.insert(pos, pl[1:])
                    pos += 1
                    offset += 1
                else:
                    # Context line - di chuyển vị trí
                    pos += 1
                i += 1
            continue

        i += 1

    return "".join(result)
