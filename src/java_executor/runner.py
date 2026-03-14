"""
Java program runner.

Takes the output of :func:`~src.java_executor.compiler.compile_java` and
executes the compiled class, capturing stdout, stderr, exit code, and
execution time.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

import config
from src.java_executor.compiler import CompilationResult


@dataclass
class RunResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    timed_out: bool = False

    @property
    def has_exception(self) -> bool:
        """True when the JVM printed an uncaught-exception stack trace."""
        return "Exception in thread" in self.stderr or "at " in self.stderr


def run_java(
    compilation: CompilationResult,
    *,
    stdin: str | None = None,
    java_path: str | None = None,
    timeout: int | None = None,
) -> RunResult:
    """
    Execute the class that was produced by *compilation*.

    Returns a :class:`RunResult` regardless of whether the program succeeds or
    crashes; callers should inspect :attr:`RunResult.success` and
    :attr:`RunResult.has_exception`.
    """
    if not compilation.success:
        raise ValueError("Cannot run code that did not compile successfully.")

    java_path = java_path or config.JAVA_PATH
    timeout = timeout or config.EXECUTION_TIMEOUT

    cmd = [
        java_path,
        "-cp", compilation.work_dir,
        compilation.class_name,
    ]

    start = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            input=stdin or "",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = -1
        stdout = ""
        stderr = f"Program execution timed out after {timeout}s."
    elapsed_ms = (time.perf_counter() - start) * 1000

    return RunResult(
        success=(exit_code == 0 and not timed_out),
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        execution_time_ms=elapsed_ms,
        timed_out=timed_out,
    )
