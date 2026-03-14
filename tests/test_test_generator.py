"""Tests for the test generator module."""

import pytest

from src.test_generator import (
    TestCase,
    TestSuite,
    generate_io_tests,
    generate_method_tests,
)


CALCULATOR_SOURCE = """
public class Calculator {
    public static int add(int a, int b) {
        return a + b;
    }

    public static int subtract(int a, int b) {
        return a - b;
    }

    public static void main(String[] args) {
        System.out.println(add(1, 2));
    }
}
"""

HELLO_SOURCE = """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""

STRING_METHOD_SOURCE = """
public class StringUtil {
    public static String greet(String name) {
        return "Hello, " + name + "!";
    }

    public static int countChars(String text) {
        return text.length();
    }
}
"""


class TestGenerateMethodTests:
    def test_generates_tests_for_calculator(self):
        suite = generate_method_tests(CALCULATOR_SOURCE)
        assert suite.class_name == "CalculatorTest"
        assert len(suite.test_cases) > 0
        assert "import org.junit.jupiter.api.Test" in suite.source_code
        assert "@Test" in suite.source_code

    def test_generates_correct_class_name(self):
        suite = generate_method_tests(CALCULATOR_SOURCE, class_name="MyCalc")
        assert suite.class_name == "MyCalcTest"

    def test_skips_main_method(self):
        suite = generate_method_tests(HELLO_SOURCE)
        # main() should not generate tests; HelloWorld has no other methods
        assert len(suite.test_cases) == 0

    def test_string_parameters(self):
        suite = generate_method_tests(STRING_METHOD_SOURCE)
        assert len(suite.test_cases) > 0
        assert "StringUtilTest" == suite.class_name

    def test_test_source_compiles_structure(self):
        suite = generate_method_tests(CALCULATOR_SOURCE)
        # Basic structural checks
        assert suite.source_code.startswith("import")
        assert "class CalculatorTest" in suite.source_code
        assert suite.source_code.strip().endswith("}")


class TestGenerateIOTests:
    def test_creates_test_cases(self):
        data = [
            {"input": "5\n3\n", "expected_output": "8", "description": "Add 5+3"},
            {"input": "10\n2\n", "expected_output": "12"},
        ]
        cases = generate_io_tests(CALCULATOR_SOURCE, data)
        assert len(cases) == 2
        assert cases[0].input_value == "5\n3\n"
        assert cases[0].expected_output == "8"
        assert cases[0].description == "Add 5+3"

    def test_empty_test_cases(self):
        cases = generate_io_tests(CALCULATOR_SOURCE, [])
        assert len(cases) == 0

    def test_default_description(self):
        data = [{"input": "1", "expected_output": "1"}]
        cases = generate_io_tests(CALCULATOR_SOURCE, data)
        assert "I/O test case" in cases[0].description
