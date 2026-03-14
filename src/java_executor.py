"""Java Code Executor - Compiles and runs Java source code."""

import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field


@dataclass
class CompilationResult:
    """Result of compiling Java source code."""

    success: bool
    errors: str = ""
    class_name: str = ""
    working_dir: str = ""


@dataclass
class ExecutionResult:
    """Result of executing compiled Java code."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    timed_out: bool = False


def _extract_class_name(source_code: str) -> str:
    """Extract the public class name from Java source code.

    Scans for 'public class <Name>' pattern.  Falls back to the first
    'class <Name>' found if no public class exists.
    """
    import re

    # Try public class first
    match = re.search(r"\bpublic\s+class\s+(\w+)", source_code)
    if match:
        return match.group(1)
    # Fallback to any class
    match = re.search(r"\bclass\s+(\w+)", source_code)
    if match:
        return match.group(1)
    return ""


def compile_java(source_code: str, working_dir: str | None = None) -> CompilationResult:
    """Compile Java source code to bytecode.

    Args:
        source_code: The Java source code string.
        working_dir: Optional directory to use.  A temp directory is created
                     when not provided.

    Returns:
        A CompilationResult with success status and any error messages.
    """
    class_name = _extract_class_name(source_code)
    if not class_name:
        return CompilationResult(
            success=False,
            errors="Could not determine class name from source code.",
        )

    if working_dir is None:
        working_dir = tempfile.mkdtemp(prefix="java_exec_")

    source_file = os.path.join(working_dir, f"{class_name}.java")
    with open(source_file, "w", encoding="utf-8") as f:
        f.write(source_code)

    try:
        result = subprocess.run(
            ["javac", source_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=working_dir,
        )
    except FileNotFoundError:
        return CompilationResult(
            success=False,
            errors="javac not found. Please install a JDK.",
        )
    except subprocess.TimeoutExpired:
        return CompilationResult(
            success=False,
            errors="Compilation timed out after 30 seconds.",
        )

    if result.returncode != 0:
        return CompilationResult(
            success=False,
            errors=result.stderr,
            class_name=class_name,
            working_dir=working_dir,
        )

    return CompilationResult(
        success=True,
        class_name=class_name,
        working_dir=working_dir,
    )


def run_java(
    class_name: str,
    working_dir: str,
    stdin_input: str = "",
    timeout: int = 10,
) -> ExecutionResult:
    """Run a compiled Java class.

    Args:
        class_name: Name of the compiled class (without .class extension).
        working_dir: Directory containing the compiled .class file.
        stdin_input: Optional string to feed to the program's stdin.
        timeout: Maximum seconds the program may run.

    Returns:
        An ExecutionResult with stdout, stderr and return code.
    """
    try:
        result = subprocess.run(
            ["java", "-cp", working_dir, class_name],
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_input if stdin_input else None,
        )
    except FileNotFoundError:
        return ExecutionResult(
            success=False,
            stderr="java not found. Please install a JRE/JDK.",
            return_code=-1,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            stderr=f"Execution timed out after {timeout} seconds.",
            return_code=-1,
            timed_out=True,
        )

    return ExecutionResult(
        success=result.returncode == 0,
        stdout=result.stdout,
        stderr=result.stderr,
        return_code=result.returncode,
    )


def compile_and_run(
    source_code: str,
    stdin_input: str = "",
    timeout: int = 10,
) -> tuple[CompilationResult, ExecutionResult | None]:
    """Convenience helper: compile then run in one call.

    Returns:
        A tuple of (CompilationResult, ExecutionResult or None).
        ExecutionResult is None when compilation fails.
    """
    comp = compile_java(source_code)
    if not comp.success:
        return comp, None
    exec_result = run_java(comp.class_name, comp.working_dir, stdin_input, timeout)
    return comp, exec_result
