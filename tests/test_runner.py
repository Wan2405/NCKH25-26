"""
Tests for the Java program runner.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from src.java_executor.compiler import compile_java
from src.java_executor.runner import run_java

os.makedirs(config.WORKSPACE_DIR, exist_ok=True)


PRINT_HELLO = """\
public class PrintHello {
    public static void main(String[] args) {
        System.out.println("Hello Runner");
    }
}
"""

READ_STDIN = """\
import java.util.Scanner;
public class ReadStdin {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String line = sc.nextLine();
        System.out.println("Got: " + line);
    }
}
"""

THROWS_EXCEPTION = """\
public class ThrowsException {
    public static void main(String[] args) {
        String s = null;
        System.out.println(s.length());
    }
}
"""

EXIT_NONZERO = """\
public class ExitNonZero {
    public static void main(String[] args) {
        System.exit(42);
    }
}
"""


def test_run_success():
    compilation = compile_java(PRINT_HELLO)
    assert compilation.success
    result = run_java(compilation)
    assert result.success
    assert "Hello Runner" in result.stdout


def test_run_with_stdin():
    compilation = compile_java(READ_STDIN)
    assert compilation.success
    result = run_java(compilation, stdin="world\n")
    assert result.success
    assert "Got: world" in result.stdout


def test_run_raises_when_compile_failed():
    compilation = compile_java("not valid java { }")
    assert not compilation.success
    with pytest.raises(ValueError):
        run_java(compilation)


def test_run_runtime_exception():
    compilation = compile_java(THROWS_EXCEPTION)
    assert compilation.success
    result = run_java(compilation)
    assert not result.success
    assert result.has_exception


def test_run_nonzero_exit():
    compilation = compile_java(EXIT_NONZERO)
    assert compilation.success
    result = run_java(compilation)
    assert not result.success
    assert result.exit_code == 42
