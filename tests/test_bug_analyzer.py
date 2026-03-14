"""Tests for the bug analyzer module."""

import pytest

from src.bug_analyzer import (
    BugReport,
    ErrorType,
    analyze_compilation_errors,
    analyze_output,
    analyze_runtime_errors,
)


class TestAnalyzeCompilationErrors:
    def test_missing_semicolon(self):
        stderr = "Main.java:3: error: ';' expected\n        int x = 10\n                  ^\n"
        bugs = analyze_compilation_errors(stderr)
        assert len(bugs) == 1
        assert bugs[0].error_type == ErrorType.COMPILATION
        assert bugs[0].line_number == 3
        assert "';'" in bugs[0].message or "expected" in bugs[0].message
        assert bugs[0].suggestion != ""

    def test_cannot_find_symbol_variable(self):
        stderr = (
            "Main.java:5: error: cannot find symbol\n"
            "        System.out.println(y);\n"
            "                          ^\n"
            "  symbol:   variable y\n"
            "  location: class Main\n"
        )
        bugs = analyze_compilation_errors(stderr)
        assert len(bugs) == 1
        assert bugs[0].line_number == 5
        assert "cannot find symbol" in bugs[0].message

    def test_multiple_errors(self):
        stderr = (
            "Main.java:3: error: ';' expected\n"
            "        int x = 10\n"
            "                  ^\n"
            "Main.java:5: error: cannot find symbol\n"
            "        System.out.println(y);\n"
            "                          ^\n"
        )
        bugs = analyze_compilation_errors(stderr)
        assert len(bugs) == 2
        assert bugs[0].line_number == 3
        assert bugs[1].line_number == 5

    def test_empty_stderr(self):
        bugs = analyze_compilation_errors("")
        assert len(bugs) == 0

    def test_unrecognized_error_format(self):
        stderr = "Some unknown error happened"
        bugs = analyze_compilation_errors(stderr)
        assert len(bugs) == 1
        assert bugs[0].error_type == ErrorType.COMPILATION

    def test_incompatible_types(self):
        stderr = 'Main.java:3: error: incompatible types: String cannot be converted to int\n'
        bugs = analyze_compilation_errors(stderr)
        assert len(bugs) == 1
        assert "incompatible types" in bugs[0].message
        assert bugs[0].suggestion != ""


class TestAnalyzeRuntimeErrors:
    def test_null_pointer(self):
        stderr = (
            "Exception in thread \"main\" java.lang.NullPointerException\n"
            "\tat Main.main(Main.java:5)\n"
        )
        bugs = analyze_runtime_errors(stderr)
        assert len(bugs) == 1
        assert bugs[0].error_type == ErrorType.RUNTIME
        assert "NullPointerException" in bugs[0].message
        assert bugs[0].line_number == 5
        assert bugs[0].suggestion != ""

    def test_array_index_out_of_bounds(self):
        stderr = (
            "Exception in thread \"main\" java.lang.ArrayIndexOutOfBoundsException: "
            "Index 5 out of bounds for length 5\n"
            "\tat Main.main(Main.java:7)\n"
        )
        bugs = analyze_runtime_errors(stderr)
        assert len(bugs) == 1
        assert "ArrayIndexOutOfBoundsException" in bugs[0].message
        assert bugs[0].line_number == 7

    def test_stack_overflow(self):
        stderr = (
            "Exception in thread \"main\" java.lang.StackOverflowError\n"
            "\tat Main.recurse(Main.java:3)\n"
        )
        bugs = analyze_runtime_errors(stderr)
        assert len(bugs) == 1
        assert "StackOverflowError" in bugs[0].message
        assert "recursion" in bugs[0].suggestion.lower()

    def test_division_by_zero(self):
        stderr = (
            "Exception in thread \"main\" java.lang.ArithmeticException: / by zero\n"
            "\tat Main.main(Main.java:4)\n"
        )
        bugs = analyze_runtime_errors(stderr)
        assert len(bugs) == 1
        assert "ArithmeticException" in bugs[0].message
        assert "zero" in bugs[0].suggestion.lower()

    def test_empty_stderr(self):
        bugs = analyze_runtime_errors("")
        assert len(bugs) == 0


class TestAnalyzeOutput:
    def test_matching_output(self):
        bugs = analyze_output("Hello World", "Hello World")
        assert len(bugs) == 0

    def test_matching_output_with_whitespace(self):
        bugs = analyze_output("Hello World\n", "Hello World\n  ")
        assert len(bugs) == 0

    def test_mismatched_output(self):
        bugs = analyze_output("Hello World", "Hello world")
        assert len(bugs) == 1
        assert bugs[0].error_type == ErrorType.LOGICAL
        assert "mismatch" in bugs[0].message.lower()

    def test_empty_expected(self):
        bugs = analyze_output("", "some output")
        assert len(bugs) == 1
