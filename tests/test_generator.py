"""
Tests for the test generator.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.test_generator.generator import (
    _extract_class_name,
    _parse_public_methods,
    generate_template_tests,
    generate_tests,
)


CALCULATOR = """\
public class Calculator {
    public int add(int a, int b) { return a + b; }
    public static double divide(double a, double b) { return a / b; }
    public boolean isEven(int n) { return n % 2 == 0; }
    public void reset() {}
}
"""

EMPTY_CLASS = """\
public class Empty {}
"""


def test_extract_class_name():
    assert _extract_class_name(CALCULATOR) == "Calculator"
    assert _extract_class_name(EMPTY_CLASS) == "Empty"
    assert _extract_class_name("// no class") == "Main"


def test_parse_methods_finds_methods():
    methods = _parse_public_methods(CALCULATOR)
    names = {m.name for m in methods}
    assert "add" in names
    assert "divide" in names
    assert "isEven" in names
    assert "reset" in names


def test_generate_template_tests_structure():
    result = generate_template_tests(CALCULATOR)
    assert "import org.junit.jupiter.api.Test" in result
    assert "class CalculatorTest" in result
    assert "@Test" in result


def test_generate_template_tests_empty_class():
    result = generate_template_tests(EMPTY_CLASS)
    assert "class EmptyTest" in result
    assert "@Test" in result
    # Should have at least the placeholder
    assert "assertTrue" in result or "assertNotNull" in result or "assertDoesNotThrow" in result


def test_generate_tests_without_llm():
    result = generate_tests(CALCULATOR, llm_client=None, use_llm=False)
    assert "class CalculatorTest" in result


def test_generate_tests_with_no_llm_configured(monkeypatch):
    """When use_llm=True but no client is passed, falls back to template."""
    result = generate_tests(CALCULATOR, llm_client=None, use_llm=True)
    # Falls back to template strategy
    assert "class CalculatorTest" in result
