"""
Tests for the bug analyzer.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from src.bug_analyzer.analyzer import analyze, analyze_compilation, analyze_runtime
from src.java_executor.compiler import compile_java
from src.java_executor.runner import RunResult, run_java

os.makedirs(config.WORKSPACE_DIR, exist_ok=True)


GOOD_CODE = """\
public class GoodCode {
    public static void main(String[] args) {
        System.out.println("OK");
    }
}
"""

BAD_COMPILE = """\
public class BadCompile {
    public static void main(String[] args) {
        int x = 5
    }
}
"""

NPE_CODE = """\
public class NPECode {
    public static void main(String[] args) {
        String s = null;
        System.out.println(s.length());
    }
}
"""


def test_analyze_compilation_success():
    result = compile_java(GOOD_CODE)
    report = analyze_compilation(result)
    assert not report.has_bugs


def test_analyze_compilation_failure():
    result = compile_java(BAD_COMPILE)
    report = analyze_compilation(result)
    assert report.has_bugs
    assert len(report.bugs) > 0
    assert report.bugs[0].kind == "compile_error"


def test_analyze_runtime_success():
    comp = compile_java(GOOD_CODE)
    run = run_java(comp)
    report = analyze_runtime(run)
    assert not report.has_bugs


def test_analyze_runtime_npe():
    comp = compile_java(NPE_CODE)
    run = run_java(comp)
    report = analyze_runtime(run)
    assert report.has_bugs
    assert report.bugs[0].kind == "runtime_exception"
    assert "NullPointerException" in report.bugs[0].description
    assert "null" in report.bugs[0].suggestion.lower()


def test_analyze_timeout():
    fake_run = RunResult(
        success=False,
        stdout="",
        stderr="",
        exit_code=-1,
        execution_time_ms=15000,
        timed_out=True,
    )
    report = analyze_runtime(fake_run)
    assert report.has_bugs
    assert report.bugs[0].kind == "timeout"


def test_analyze_convenience():
    comp = compile_java(BAD_COMPILE)
    report = analyze(comp)
    assert report.has_bugs


def test_bug_report_as_text():
    comp = compile_java(BAD_COMPILE)
    report = analyze_compilation(comp)
    text = report.as_text()
    assert "compile_error" in text


def test_no_bugs_as_text():
    comp = compile_java(GOOD_CODE)
    report = analyze_compilation(comp)
    assert report.as_text() == "No bugs detected."
