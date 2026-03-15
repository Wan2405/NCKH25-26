"""
CODE SANITIZER
==============
Utilities to clean and validate LLM-generated Java code before it is
compiled or saved to disk.

LLMs (e.g. Qwen2.5-Coder, Llama 3.1 via Ollama) frequently return Java
code with artefacts that cause COMPILE_ERROR or RUNTIME_ERROR when the
code is fed directly into javac:

* Markdown code fences  (```java … ```)
* Introductory prose    ("Here is the fixed code:\n…")
* Wrong class name      (LLM renames the class, which must match the file)

``sanitize_java_code`` applies all clean-up steps in order and is the
single entry-point that every pipeline component should use.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Đã sửa lại Regex chuẩn xác, không bị lỗi hiển thị
_FENCE_RE = re.compile(r"`{3}(?:java|Java)?\s*\n?(.*?)`{3}", re.DOTALL)

# Matches the first  public class <Name>  declaration
_CLASS_DECL_RE = re.compile(r"(public\s+class\s+)\w+")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def strip_markdown_fences(code: str) -> str:
    """Remove the outermost markdown code fence from *code* if present.

    If no fence is found the original string is returned unchanged.
    All leading and trailing newlines are stripped from the extracted
    content (the fenced block typically starts/ends with a newline).
    """
    m = _FENCE_RE.search(code)
    if m:
        return m.group(1).strip("\n")
    return code


def strip_preamble(code: str) -> str:
    """Drop any leading prose that appears before the first Java keyword.

    LLMs sometimes prefix the code with a sentence like
    "Here is the corrected version:". This function discards everything
    before the first line that looks like it belongs to a Java file
    (``package``, ``import``, ``public``, ``//``, ``/*``).
    """
    java_starters = re.compile(
        r"^\s*(package |import |public |//|/\*|class )", re.MULTILINE
    )
    m = java_starters.search(code)
    if m and m.start() > 0:
        return code[m.start():]
    return code


def enforce_class_name(code: str, expected_class: str) -> str:
    """Replace the first ``public class <X>`` declaration so the class name
    equals *expected_class*.

    This prevents the Java compiler from rejecting the file because the
    class name does not match the filename (a frequent RUNTIME_ERROR
    symptom after an LLM-generated fix).

    Returns *code* unchanged when *expected_class* is empty/falsy.
    """
    if not expected_class:
        return code
    return _CLASS_DECL_RE.sub(r"\g<1>" + expected_class, code, count=1)


def keep_only_first_class(code: str, expected_class: str | None = None) -> str:
    """Remove all classes except the first one (the target class).
    
    LLMs sometimes include test classes or other classes in the response.
    This function keeps only the first public class and removes everything else
    that comes after the closing brace of that class.
    
    Args:
        code: Raw Java source code
        expected_class: The class name to expect (if provided, validates it matches)
    
    Returns:
        Code containing only the first public class
    """
    # Find the first public class declaration (supports missing 'public')
    class_pattern = r"(?:public\s+)?class\s+(\w+)"
    match = re.search(class_pattern, code)
    
    if not match:
        return code
    
    class_start = match.start()
    class_name = match.group(1)
    
    # If expected_class is provided, validate
    if expected_class and class_name != expected_class:
        logger.warning(
            f"Expected class name '{expected_class}' but found '{class_name}'"
        )
    
    # Find the opening brace of the class
    open_brace_pos = code.find("{", class_start)
    if open_brace_pos == -1:
        return code
    
    # Count braces to find the closing brace of the class
    brace_count = 0
    last_close_brace = -1
    in_string = False
    in_char = False
    
    i = open_brace_pos
    while i < len(code):
        # Skip single-line comments (//)
        if not in_string and not in_char and code[i:i+2] == "//":
            i = code.find("\n", i)
            if i == -1: break
            continue
            
        # Skip multi-line comments (/* ... */)
        if not in_string and not in_char and code[i:i+2] == "/*":
            i = code.find("*/", i + 2)
            if i == -1: break
            i += 2
            continue
            
        char = code[i]
        
        # Handle string literals to avoid counting braces inside strings/chars
        if char == '"' and (i == 0 or code[i-1] != '\\') and not in_char:
            in_string = not in_string
        elif char == "'" and (i == 0 or code[i-1] != '\\') and not in_string:
            in_char = not in_char
            
        # Only count braces outside of strings and chars
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
    
    # Lấy chính xác từ lúc bắt đầu class đến hết class
    first_class_code = code[class_start:last_close_brace + 1]
    
    # Lấy toàn bộ phần đầu (package, imports...)
    preamble = code[:class_start]
    
    return preamble + first_class_code


def sanitize_java_code(code: str, expected_class: str | None = None) -> str:
    """Clean an LLM-generated Java code string.

    Steps applied in order:

    1. Strip markdown code fences.
    2. Strip leading prose / preamble text.
    3. Keep only the first public class (remove test classes, etc).
    4. Strip trailing whitespace.
    5. Enforce *expected_class* as the public class name (optional).

    If the sanitized result no longer contains the ``class`` keyword the
    original *code* is returned with a warning so that the caller can
    decide what to do next (e.g. retry the LLM).

    Args:
        code:           Raw string returned by the LLM.
        expected_class: Java class name that the file must declare (e.g.
                        ``"P001_TongHaiSo"``).  Pass ``None`` or ``""``
                        to skip class-name enforcement.

    Returns:
        Cleaned Java source code string.
    """
    if not code or not code.strip():
        return code

    cleaned = strip_markdown_fences(code)
    cleaned = strip_preamble(cleaned)
    cleaned = keep_only_first_class(cleaned, expected_class)
    cleaned = cleaned.strip()

    if expected_class:
        cleaned = enforce_class_name(cleaned, expected_class)

    # Sanity-check: the result must look like Java source
    if not re.search(r'\bclass\s+', cleaned):
        logger.warning(
            "Sanitized code does not contain a 'class' keyword – "
            "returning original code to avoid data loss."
        )
        return code

    return cleaned