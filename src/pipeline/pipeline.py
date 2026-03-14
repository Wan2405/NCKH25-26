"""
Automated Testing & Debugging Pipeline.

Orchestrates the full workflow:

1. Compile the submitted Java source code.
2. (optional) Run the compiled program.
3. Analyse errors.
4. If errors are found, ask the LLM to fix them, then retry (up to
   ``max_iterations`` times).
5. Generate a JUnit 5 test class for the (fixed) code.
6. Return a :class:`PipelineResult` with every intermediate artefact.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import List, Optional

import config
from src.bug_analyzer.analyzer import BugReport, analyze
from src.java_executor.compiler import CompilationResult, compile_java
from src.java_executor.runner import RunResult, run_java
from src.llm_client.client import LLMClient
from src.test_generator.generator import generate_tests


@dataclass
class IterationRecord:
    """Holds the artefacts produced in one fix iteration."""
    iteration: int
    source_code: str
    compilation: CompilationResult
    run: Optional[RunResult]
    bug_report: BugReport


@dataclass
class PipelineResult:
    """Final result returned by :func:`run_pipeline`."""
    original_code: str
    final_code: str
    fixed: bool
    iterations: List[IterationRecord] = field(default_factory=list)
    generated_tests: str = ""
    error_message: str = ""

    @property
    def total_iterations(self) -> int:
        return len(self.iterations)

    def summary(self) -> str:
        lines = [
            f"Fixed: {self.fixed}",
            f"Iterations: {self.total_iterations}",
        ]
        if self.fixed:
            lines.append("The code compiles and runs successfully.")
        else:
            last = self.iterations[-1] if self.iterations else None
            if last:
                lines.append(f"Last bug report: {last.bug_report.summary}")
        return "\n".join(lines)


# ── helpers ───────────────────────────────────────────────────────────────────

def _ensure_workspace(workspace_dir: str) -> None:
    os.makedirs(workspace_dir, exist_ok=True)


def _cleanup_work_dir(work_dir: str) -> None:
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass


# ── main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    source_code: str,
    *,
    llm_client: Optional[LLMClient] = None,
    stdin: Optional[str] = None,
    max_iterations: int | None = None,
    workspace_dir: str | None = None,
    generate_unit_tests: bool = True,
    cleanup: bool = True,
) -> PipelineResult:
    """
    Run the full testing & debugging pipeline on *source_code*.

    Parameters
    ----------
    source_code:
        The Java source code to process (single public class).
    llm_client:
        Optional LLM client for test generation and auto-fixing.
        If ``None`` a new :class:`LLMClient` is instantiated (which uses
        environment-variable configuration).
    stdin:
        Optional stdin fed to the program during execution.
    max_iterations:
        Maximum number of LLM fix iterations.  Defaults to
        ``config.MAX_FIX_ITERATIONS``.
    workspace_dir:
        Directory used for temporary compilation artefacts.
    generate_unit_tests:
        Whether to generate a JUnit 5 test class for the (fixed) code.
    cleanup:
        Whether to delete the temporary compilation directories when done.
    """
    if llm_client is None:
        llm_client = LLMClient()

    max_iterations = max_iterations if max_iterations is not None else config.MAX_FIX_ITERATIONS
    workspace_dir = workspace_dir or config.WORKSPACE_DIR
    _ensure_workspace(workspace_dir)

    current_code = source_code
    iterations: List[IterationRecord] = []
    work_dirs: List[str] = []

    for iteration in range(max_iterations + 1):
        # ── 1. Compile ────────────────────────────────────────────────────────
        compilation = compile_java(current_code, workspace_dir=workspace_dir)
        work_dirs.append(compilation.work_dir)

        # ── 2. Run (only if compilation succeeded) ────────────────────────────
        run: Optional[RunResult] = None
        if compilation.success:
            run = run_java(compilation, stdin=stdin)

        # ── 3. Analyse ────────────────────────────────────────────────────────
        bug_report = analyze(compilation, run)

        record = IterationRecord(
            iteration=iteration,
            source_code=current_code,
            compilation=compilation,
            run=run,
            bug_report=bug_report,
        )
        iterations.append(record)

        # ── 4. Done? ──────────────────────────────────────────────────────────
        if not bug_report.has_bugs:
            break

        # ── 5. Last iteration exhausted – stop ────────────────────────────────
        if iteration >= max_iterations:
            break

        # ── 6. Ask LLM to fix the code ────────────────────────────────────────
        bug_description = bug_report.as_text()
        fixed_code = llm_client.fix_code(current_code, bug_description)

        # Strip accidental markdown fences that some LLMs add
        fixed_code = _strip_fences(fixed_code)

        if fixed_code.strip() == current_code.strip():
            # LLM returned the same code – no progress, stop early
            break

        current_code = fixed_code

    # ── 7. Generate unit tests for the final (fixed or original) code ─────────
    final_record = iterations[-1]
    tests_source = ""
    if generate_unit_tests:
        final_code = final_record.source_code if final_record.bug_report.has_bugs else current_code
        tests_source = generate_tests(final_code, llm_client)

    # Cleanup temp directories
    if cleanup:
        for d in work_dirs:
            _cleanup_work_dir(d)

    fixed = not final_record.bug_report.has_bugs

    return PipelineResult(
        original_code=source_code,
        final_code=current_code,
        fixed=fixed,
        iterations=iterations,
        generated_tests=tests_source,
    )


def _strip_fences(code: str) -> str:
    """Remove ``` or ```java fences that LLMs sometimes include."""
    import re
    code = re.sub(r"^```(?:java)?\n?", "", code.strip(), flags=re.MULTILINE)
    code = re.sub(r"\n?```$", "", code.strip(), flags=re.MULTILINE)
    return code.strip()
