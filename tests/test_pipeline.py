"""
Tests for the automated pipeline.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from src.pipeline.pipeline import run_pipeline, _strip_fences

os.makedirs(config.WORKSPACE_DIR, exist_ok=True)


CORRECT_CODE = """\
public class CorrectCode {
    public static int square(int n) { return n * n; }
    public static void main(String[] args) {
        System.out.println(square(5));
    }
}
"""

# One compile error: missing semicolon – no LLM can fix this in the test run
# (we're not mocking the LLM), so we expect it to remain unfixed.
COMPILE_ERROR_CODE = """\
public class HasCompileError {
    public static void main(String[] args) {
        int x = 10
        System.out.println(x);
    }
}
"""

RUNTIME_ERROR_CODE = """\
public class HasRuntimeError {
    public static void main(String[] args) {
        int[] arr = new int[3];
        System.out.println(arr[10]);
    }
}
"""


def test_pipeline_correct_code():
    result = run_pipeline(CORRECT_CODE, max_iterations=0)
    assert result.fixed
    assert result.total_iterations == 1
    assert result.final_code == CORRECT_CODE


def test_pipeline_compile_error():
    result = run_pipeline(COMPILE_ERROR_CODE, max_iterations=0)
    assert not result.fixed
    first = result.iterations[0]
    assert not first.compilation.success
    assert first.bug_report.has_bugs


def test_pipeline_runtime_error():
    result = run_pipeline(RUNTIME_ERROR_CODE, max_iterations=0)
    assert not result.fixed
    first = result.iterations[0]
    assert first.compilation.success
    assert first.run is not None
    assert not first.run.success


def test_pipeline_generates_tests():
    result = run_pipeline(CORRECT_CODE, generate_unit_tests=True, max_iterations=0)
    assert result.generated_tests
    assert "Test" in result.generated_tests


def test_pipeline_summary_fixed():
    result = run_pipeline(CORRECT_CODE, max_iterations=0)
    summary = result.summary()
    assert "Fixed: True" in summary


def test_pipeline_summary_not_fixed():
    result = run_pipeline(COMPILE_ERROR_CODE, max_iterations=0)
    summary = result.summary()
    assert "Fixed: False" in summary


def test_strip_fences():
    code = "```java\npublic class Foo {}\n```"
    assert _strip_fences(code) == "public class Foo {}"


def test_strip_fences_no_fences():
    code = "public class Foo {}"
    assert _strip_fences(code) == code
