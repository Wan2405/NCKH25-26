"""
Tests for the Java compiler wrapper.
"""
import os
import sys
import pytest

# Make root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from src.java_executor.compiler import compile_java, _extract_class_name, _parse_diagnostics

# Ensure workspace exists for tests
os.makedirs(config.WORKSPACE_DIR, exist_ok=True)


HELLO_WORLD = """\
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""

MISSING_SEMICOLON = """\
public class BadCode {
    public static void main(String[] args) {
        int x = 5
        System.out.println(x);
    }
}
"""

UNKNOWN_SYMBOL = """\
public class BadCode {
    public static void main(String[] args) {
        System.out.println(undeclaredVariable);
    }
}
"""


def test_compile_success():
    result = compile_java(HELLO_WORLD)
    assert result.success is True
    assert result.class_name == "HelloWorld"
    assert len(result.errors) == 0


def test_compile_missing_semicolon():
    result = compile_java(MISSING_SEMICOLON)
    assert result.success is False
    assert len(result.errors) > 0
    # The error should mention ';'
    assert any(";" in d.message or "expected" in d.message for d in result.errors)


def test_compile_unknown_symbol():
    result = compile_java(UNKNOWN_SYMBOL)
    assert result.success is False
    assert any("cannot find symbol" in d.message for d in result.errors)


def test_extract_class_name_public():
    source = "public class MyClass { }"
    assert _extract_class_name(source) == "MyClass"


def test_extract_class_name_fallback():
    source = "class AnotherClass { }"
    assert _extract_class_name(source) == "AnotherClass"


def test_extract_class_name_default():
    assert _extract_class_name("// no class here") == "Main"


def test_parse_diagnostics_empty():
    assert _parse_diagnostics("") == []


def test_compile_creates_work_dir():
    result = compile_java(HELLO_WORLD)
    assert os.path.isdir(result.work_dir)
