"""Tests for the Java executor module."""

import os
import pytest

from src.java_executor import (
    CompilationResult,
    ExecutionResult,
    compile_and_run,
    compile_java,
    run_java,
    _extract_class_name,
)


class TestExtractClassName:
    def test_public_class(self):
        assert _extract_class_name("public class Foo {}") == "Foo"

    def test_non_public_class(self):
        assert _extract_class_name("class Bar {}") == "Bar"

    def test_public_preferred(self):
        code = "class Helper {} public class Main {}"
        assert _extract_class_name(code) == "Main"

    def test_no_class(self):
        assert _extract_class_name("int x = 5;") == ""


class TestCompileJava:
    def test_valid_code_compiles(self):
        code = 'public class Hello { public static void main(String[] args) { System.out.println("Hi"); } }'
        result = compile_java(code)
        assert result.success is True
        assert result.class_name == "Hello"
        assert os.path.exists(os.path.join(result.working_dir, "Hello.class"))

    def test_invalid_code_fails(self):
        code = "public class Bad { public static void main(String[] args) { int x = } }"
        result = compile_java(code)
        assert result.success is False
        assert result.errors != ""

    def test_no_class_name(self):
        code = "int x = 5;"
        result = compile_java(code)
        assert result.success is False
        assert "class name" in result.errors.lower()


class TestRunJava:
    def test_run_hello_world(self):
        code = 'public class RunHello { public static void main(String[] args) { System.out.println("Hello"); } }'
        comp = compile_java(code)
        assert comp.success
        result = run_java(comp.class_name, comp.working_dir)
        assert result.success is True
        assert "Hello" in result.stdout

    def test_run_with_stdin(self):
        code = (
            "import java.util.Scanner;\n"
            "public class ReadInput {\n"
            "  public static void main(String[] args) {\n"
            "    Scanner s = new Scanner(System.in);\n"
            "    System.out.println(s.nextLine());\n"
            "    s.close();\n"
            "  }\n"
            "}"
        )
        comp = compile_java(code)
        assert comp.success
        result = run_java(comp.class_name, comp.working_dir, stdin_input="test input")
        assert result.success is True
        assert "test input" in result.stdout

    def test_runtime_error_captured(self):
        code = (
            "public class DivZero {\n"
            "  public static void main(String[] args) {\n"
            "    int x = 1 / 0;\n"
            "  }\n"
            "}"
        )
        comp = compile_java(code)
        assert comp.success
        result = run_java(comp.class_name, comp.working_dir)
        assert result.success is False
        assert "ArithmeticException" in result.stderr


class TestCompileAndRun:
    def test_success_flow(self):
        code = 'public class CAR { public static void main(String[] args) { System.out.println("OK"); } }'
        comp, exec_result = compile_and_run(code)
        assert comp.success is True
        assert exec_result is not None
        assert exec_result.success is True
        assert "OK" in exec_result.stdout

    def test_compile_failure_returns_none(self):
        code = "public class BadCAR { invalid }"
        comp, exec_result = compile_and_run(code)
        assert comp.success is False
        assert exec_result is None
