"""
Bug analyzer.

Parses raw compiler output and JVM runtime output to produce structured
:class:`BugReport` objects that the LLM or the fix engine can act on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from src.java_executor.compiler import CompilationResult
from src.java_executor.runner import RunResult


@dataclass
class Bug:
    kind: str          # "compile_error" | "runtime_exception" | "assertion_failure" | "timeout"
    description: str
    line: int = 0
    suggestion: str = ""


@dataclass
class BugReport:
    has_bugs: bool
    bugs: List[Bug] = field(default_factory=list)
    summary: str = ""

    def as_text(self) -> str:
        if not self.has_bugs:
            return "No bugs detected."
        parts = [self.summary]
        for i, bug in enumerate(self.bugs, 1):
            parts.append(f"{i}. [{bug.kind}] line {bug.line}: {bug.description}")
            if bug.suggestion:
                parts.append(f"   Suggestion: {bug.suggestion}")
        return "\n".join(parts)


# ── common Java error → plain-English suggestion map ─────────────────────────

_COMPILE_HINTS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"cannot find symbol"), "Check that the variable/method/class is declared and the spelling is correct."),
    (re.compile(r"incompatible types"), "A value of the wrong type is being assigned or passed. Check your casts and variable types."),
    (re.compile(r"missing return statement"), "Ensure every code path in a non-void method returns a value."),
    (re.compile(r"reached end of file while parsing"), "A closing brace `}` is missing."),
    (re.compile(r"illegal start of expression"), "There may be an extra or misplaced `{`, `}`, `;`, or keyword."),
    (re.compile(r"';' expected"), "A semicolon is missing at the end of a statement."),
    (re.compile(r"class .* is public, should be declared in a file named"), "The public class name must match the file name."),
    (re.compile(r"variable .* might not have been initialized"), "Initialise the variable before use."),
    (re.compile(r"method .* in class .* cannot be applied"), "The argument types or count do not match the method signature."),
    (re.compile(r"operator .* cannot be applied to"), "An operator is used with incompatible operand types."),
]

_RUNTIME_HINTS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"NullPointerException"), "An object reference is null. Add a null check before dereferencing."),
    (re.compile(r"ArrayIndexOutOfBoundsException"), "An array index is out of range. Check loop bounds and array size."),
    (re.compile(r"StringIndexOutOfBoundsException"), "A string index is out of range. Check the string length before indexing."),
    (re.compile(r"ClassCastException"), "An object cannot be cast to the target type. Verify the actual runtime type."),
    (re.compile(r"StackOverflowError"), "Infinite recursion detected. Add or fix the base case."),
    (re.compile(r"NumberFormatException"), "A string cannot be parsed as a number. Validate the input first."),
    (re.compile(r"ArithmeticException.*/ by zero"), "Division by zero. Check the divisor before dividing."),
    (re.compile(r"OutOfMemoryError"), "The JVM ran out of heap memory. Check for memory leaks or unbounded data structures."),
    (re.compile(r"ConcurrentModificationException"), "A collection was modified while being iterated. Use an Iterator or copy the collection."),
]


def _hint(patterns: List[tuple[re.Pattern, str]], text: str) -> str:
    for pattern, hint in patterns:
        if pattern.search(text):
            return hint
    return ""


# ── public API ────────────────────────────────────────────────────────────────

def analyze_compilation(result: CompilationResult) -> BugReport:
    """Return a :class:`BugReport` for compilation failures."""
    if result.success:
        return BugReport(has_bugs=False, summary="Compilation succeeded.")

    bugs: List[Bug] = []
    for diag in result.errors:
        bugs.append(Bug(
            kind="compile_error",
            description=diag.message,
            line=diag.line,
            suggestion=_hint(_COMPILE_HINTS, diag.message),
        ))

    # Fallback: parse raw output if no structured diagnostics were produced
    if not bugs and result.raw_output:
        bugs.append(Bug(
            kind="compile_error",
            description=result.raw_output,
            suggestion="",
        ))

    summary = f"Found {len(bugs)} compilation error(s)."
    return BugReport(has_bugs=bool(bugs), bugs=bugs, summary=summary)


def analyze_runtime(run: RunResult) -> BugReport:
    """Return a :class:`BugReport` for runtime failures."""
    if run.timed_out:
        return BugReport(
            has_bugs=True,
            bugs=[Bug(kind="timeout", description="Program exceeded the execution time limit.")],
            summary="Program timed out.",
        )

    if run.success:
        return BugReport(has_bugs=False, summary="Program ran successfully.")

    bugs: List[Bug] = []
    stderr = run.stderr

    # Extract exception class and message from first "Exception in thread" line
    exc_match = re.search(r"([\w.]+Exception|[\w.]+Error)[:\s]*(.*)", stderr)
    if exc_match:
        exc_name = exc_match.group(1).split(".")[-1]
        exc_msg = exc_match.group(2).strip().splitlines()[0] if exc_match.group(2) else ""
        description = f"{exc_name}: {exc_msg}" if exc_msg else exc_name

        # Extract line number from first "at" frame that mentions user code
        line = 0
        for frame in re.finditer(r"at [\w.$]+\([\w]+\.java:(\d+)\)", stderr):
            line = int(frame.group(1))
            break

        bugs.append(Bug(
            kind="runtime_exception",
            description=description,
            line=line,
            suggestion=_hint(_RUNTIME_HINTS, stderr),
        ))
    elif stderr.strip():
        bugs.append(Bug(
            kind="runtime_exception",
            description=stderr.strip(),
        ))

    summary = f"Found {len(bugs)} runtime error(s)." if bugs else "Program exited with non-zero code."
    return BugReport(has_bugs=bool(bugs), bugs=bugs, summary=summary)


def analyze(
    compilation: CompilationResult,
    run: RunResult | None = None,
) -> BugReport:
    """
    Convenience function: analyse compilation first; if it succeeded, also
    analyse the run result (if provided).
    """
    comp_report = analyze_compilation(compilation)
    if comp_report.has_bugs:
        return comp_report
    if run is not None:
        return analyze_runtime(run)
    return BugReport(has_bugs=False, summary="No errors detected.")
