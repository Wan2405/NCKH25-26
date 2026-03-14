"""
Tests for llm.code_sanitizer
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from llm.code_sanitizer import (
    strip_markdown_fences,
    strip_preamble,
    enforce_class_name,
    sanitize_java_code,
)

# ---------------------------------------------------------------------------
# strip_markdown_fences
# ---------------------------------------------------------------------------

SIMPLE_CODE = "public class Hello {\n    public static void main(String[] args) {}\n}"


def test_strip_fences_java():
    fenced = f"```java\n{SIMPLE_CODE}\n```"
    assert strip_markdown_fences(fenced) == SIMPLE_CODE


def test_strip_fences_no_lang():
    fenced = f"```\n{SIMPLE_CODE}\n```"
    assert strip_markdown_fences(fenced) == SIMPLE_CODE


def test_strip_fences_noop_when_no_fence():
    assert strip_markdown_fences(SIMPLE_CODE) == SIMPLE_CODE


def test_strip_fences_capital_java():
    fenced = f"```Java\n{SIMPLE_CODE}\n```"
    assert strip_markdown_fences(fenced) == SIMPLE_CODE


# ---------------------------------------------------------------------------
# strip_preamble
# ---------------------------------------------------------------------------

def test_strip_preamble_removes_prose():
    code_with_prose = "Here is the corrected Java code:\n" + SIMPLE_CODE
    result = strip_preamble(code_with_prose)
    assert result.startswith("public class")


def test_strip_preamble_noop_when_clean():
    assert strip_preamble(SIMPLE_CODE) == SIMPLE_CODE


def test_strip_preamble_keeps_import():
    code_with_import = "import java.util.*;\n" + SIMPLE_CODE
    result = strip_preamble(code_with_import)
    assert result.startswith("import")


# ---------------------------------------------------------------------------
# enforce_class_name
# ---------------------------------------------------------------------------

def test_enforce_class_name_changes_name():
    code = "public class WrongName {\n}"
    result = enforce_class_name(code, "CorrectName")
    assert "public class CorrectName" in result
    assert "WrongName" not in result


def test_enforce_class_name_noop_when_empty():
    code = "public class Foo {\n}"
    assert enforce_class_name(code, "") == code
    assert enforce_class_name(code, None) == code


def test_enforce_class_name_only_first_occurrence():
    code = "public class Outer {\n    class Inner {\n    }\n}"
    result = enforce_class_name(code, "MyOuter")
    assert "public class MyOuter" in result
    assert "class Inner" in result


# ---------------------------------------------------------------------------
# sanitize_java_code – integration
# ---------------------------------------------------------------------------

def test_sanitize_strips_fences_and_preamble():
    dirty = "Here is the fixed code:\n```java\n" + SIMPLE_CODE + "\n```"
    result = sanitize_java_code(dirty)
    assert result == SIMPLE_CODE


def test_sanitize_enforces_class_name():
    code = "public class LLMGeneratedName {\n}"
    result = sanitize_java_code(code, expected_class="P001_TongHaiSo")
    assert "public class P001_TongHaiSo" in result


def test_sanitize_returns_original_when_no_class_keyword():
    garbage = "This is not Java code at all."
    result = sanitize_java_code(garbage)
    assert result == garbage


def test_sanitize_empty_input():
    assert sanitize_java_code("") == ""
    assert sanitize_java_code("   ") == "   "


def test_sanitize_noop_on_clean_code():
    result = sanitize_java_code(SIMPLE_CODE)
    assert result == SIMPLE_CODE


def test_sanitize_full_scenario():
    """Simulate an LLM returning code with fences AND the wrong class name."""
    llm_output = (
        "Sure! Here is the corrected version:\n"
        "```java\n"
        "public class FixedByLLM {\n"
        "    public static void main(String[] args) {\n"
        '        System.out.println("Hello");\n'
        "    }\n"
        "}\n"
        "```"
    )
    result = sanitize_java_code(llm_output, expected_class="P001_TongHaiSo")
    assert "public class P001_TongHaiSo" in result
    assert "```" not in result
    assert "Sure!" not in result
