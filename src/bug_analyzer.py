"""Bug Analyzer - Parses Java compilation and runtime errors."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ErrorType(str, Enum):
    COMPILATION = "compilation"
    RUNTIME = "runtime"
    LOGICAL = "logical"


@dataclass
class BugReport:
    """A single identified bug."""

    error_type: ErrorType
    message: str
    line_number: int | None = None
    suggestion: str = ""


# ---------- Compilation-error patterns ----------

_JAVAC_ERROR_RE = re.compile(
    r"^(?P<file>.+\.java):(?P<line>\d+): error: (?P<msg>.+)$",
    re.MULTILINE,
)

_COMMON_FIXES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"cannot find symbol.*variable (\w+)", re.DOTALL),
        "Variable '{0}' is not declared. Declare it before use.",
    ),
    (
        re.compile(r"cannot find symbol.*method (\w+)", re.DOTALL),
        "Method '{0}' is not defined. Check spelling or add the method.",
    ),
    (
        re.compile(r"';' expected"),
        "Missing semicolon. Add ';' at the indicated position.",
    ),
    (
        re.compile(r"incompatible types"),
        "Type mismatch. Check the types on both sides of the assignment.",
    ),
    (
        re.compile(r"cannot be applied to"),
        "Wrong argument types passed to a method. Verify the method signature.",
    ),
    (
        re.compile(r"reached end of file while parsing"),
        "Missing closing brace '}'. Check that all blocks are properly closed.",
    ),
    (
        re.compile(r"class .+ is public, should be declared in a file named"),
        "The public class name must match the file name.",
    ),
    (
        re.compile(r"illegal start of expression"),
        "Syntax error. Check for misplaced keywords or punctuation.",
    ),
    (
        re.compile(r"array required, but (\w+) found"),
        "Attempting to index a non-array variable. Verify the variable type.",
    ),
    (
        re.compile(r"non-static method .+ cannot be referenced from a static context"),
        "Call instance methods on an object, not the class directly.",
    ),
]

# ---------- Runtime-error patterns ----------

_RUNTIME_EXCEPTION_RE = re.compile(
    r"^(?:Exception in thread .+? )?([\w.]+(?:Error|Exception))(?:: (.+))?$",
    re.MULTILINE,
)
_RUNTIME_AT_RE = re.compile(
    r"\tat .+\((?P<file>\w+\.java):(?P<line>\d+)\)",
)

_RUNTIME_FIXES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"NullPointerException"),
        "A variable is null when used. Add null checks before access.",
    ),
    (
        re.compile(r"ArrayIndexOutOfBoundsException"),
        "Array index is out of range. Verify loop bounds and array sizes.",
    ),
    (
        re.compile(r"StringIndexOutOfBoundsException"),
        "String index is out of range. Check string length before accessing.",
    ),
    (
        re.compile(r"StackOverflowError"),
        "Infinite recursion detected. Add or fix the base case.",
    ),
    (
        re.compile(r"ArithmeticException.*/ by zero"),
        "Division by zero. Add a check to avoid dividing by zero.",
    ),
    (
        re.compile(r"NumberFormatException"),
        "Invalid number format. Validate the string before parsing.",
    ),
    (
        re.compile(r"ClassCastException"),
        "Invalid type cast. Use instanceof before casting.",
    ),
    (
        re.compile(r"OutOfMemoryError"),
        "Out of memory. Check for memory leaks or reduce data size.",
    ),
]


def _suggest_fix(message: str, fix_patterns: list[tuple[re.Pattern[str], str]]) -> str:
    """Return a suggestion for the given error message, if any."""
    for pattern, template in fix_patterns:
        m = pattern.search(message)
        if m:
            groups = m.groups()
            if groups:
                return template.format(*groups)
            return template
    return ""


def analyze_compilation_errors(stderr: str) -> list[BugReport]:
    """Parse javac stderr and return a list of BugReports."""
    reports: list[BugReport] = []
    for match in _JAVAC_ERROR_RE.finditer(stderr):
        msg = match.group("msg")
        line = int(match.group("line"))
        suggestion = _suggest_fix(msg, _COMMON_FIXES)
        # Also check multi-line context for better suggestions
        idx = match.end()
        context_end = stderr.find("\n\n", idx)
        if context_end == -1:
            context_end = len(stderr)
        context = stderr[idx:context_end]
        if not suggestion:
            suggestion = _suggest_fix(msg + " " + context, _COMMON_FIXES)
        reports.append(
            BugReport(
                error_type=ErrorType.COMPILATION,
                message=msg.strip(),
                line_number=line,
                suggestion=suggestion,
            )
        )
    # If no structured errors found, create a generic report
    if not reports and stderr.strip():
        reports.append(
            BugReport(
                error_type=ErrorType.COMPILATION,
                message=stderr.strip()[:500],
                suggestion="Review the compiler output for details.",
            )
        )
    return reports


def analyze_runtime_errors(stderr: str) -> list[BugReport]:
    """Parse JVM runtime stderr and return a list of BugReports."""
    reports: list[BugReport] = []
    for match in _RUNTIME_EXCEPTION_RE.finditer(stderr):
        exception_class = match.group(1)
        detail = match.group(2) or ""
        full_msg = f"{exception_class}: {detail}".strip(": ")
        suggestion = _suggest_fix(full_msg, _RUNTIME_FIXES)

        # Try to extract line number from stack trace
        line_number = None
        after = stderr[match.end() :]
        at_match = _RUNTIME_AT_RE.search(after)
        if at_match:
            line_number = int(at_match.group("line"))

        reports.append(
            BugReport(
                error_type=ErrorType.RUNTIME,
                message=full_msg,
                line_number=line_number,
                suggestion=suggestion,
            )
        )
    if not reports and stderr.strip():
        reports.append(
            BugReport(
                error_type=ErrorType.RUNTIME,
                message=stderr.strip()[:500],
                suggestion="Review the runtime output for details.",
            )
        )
    return reports


def analyze_output(
    expected_output: str,
    actual_output: str,
) -> list[BugReport]:
    """Compare expected vs actual output and report logical errors."""
    reports: list[BugReport] = []
    if expected_output.strip() != actual_output.strip():
        reports.append(
            BugReport(
                error_type=ErrorType.LOGICAL,
                message=(
                    f"Output mismatch.\n"
                    f"  Expected: {expected_output.strip()!r}\n"
                    f"  Actual:   {actual_output.strip()!r}"
                ),
                suggestion=(
                    "The program produces incorrect output. "
                    "Review the algorithm logic and edge cases."
                ),
            )
        )
    return reports
