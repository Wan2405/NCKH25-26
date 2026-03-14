"""Automated Pipeline - Orchestrates compilation, testing, analysis, and fixing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .bug_analyzer import (
    BugReport,
    analyze_compilation_errors,
    analyze_output,
    analyze_runtime_errors,
)
from .java_executor import CompilationResult, ExecutionResult, compile_and_run, compile_java, run_java
from .llm_client import LLMClient, LLMConfig, LLMResponse
from .test_generator import TestCase, generate_io_tests, generate_method_tests


class PipelineStage(str, Enum):
    COMPILE = "compile"
    RUN = "run"
    TEST = "test"
    ANALYZE = "analyze"
    FIX = "fix"


@dataclass
class PipelineResult:
    """Complete result of a pipeline run."""

    source_code: str
    compilation: CompilationResult | None = None
    execution: ExecutionResult | None = None
    bugs: list[BugReport] = field(default_factory=list)
    test_results: list[dict] = field(default_factory=list)
    llm_analysis: LLMResponse | None = None
    fixed_code: str | None = None
    stages_completed: list[PipelineStage] = field(default_factory=list)
    error: str = ""


async def run_pipeline(
    source_code: str,
    *,
    test_cases: list[dict[str, str]] | None = None,
    use_llm: bool = False,
    llm_config: LLMConfig | None = None,
    stdin_input: str = "",
    expected_output: str = "",
    timeout: int = 10,
) -> PipelineResult:
    """Run the full testing and debugging pipeline.

    Steps:
      1. Compile the Java source code.
      2. If compilation fails, analyze errors and optionally ask LLM to fix.
      3. If compilation succeeds, run the program.
      4. Run any provided I/O test cases.
      5. Analyze runtime errors or output mismatches.
      6. Optionally use LLM for deeper analysis.

    Args:
        source_code: Java source code to test.
        test_cases: Optional list of I/O test case dicts.
        use_llm: Whether to use LLM for analysis/fixing.
        llm_config: LLM configuration (uses env vars if None).
        stdin_input: Default stdin input for execution.
        expected_output: Expected stdout for comparison.
        timeout: Execution timeout in seconds.

    Returns:
        A PipelineResult summarizing everything.
    """
    result = PipelineResult(source_code=source_code)

    # --- Stage 1: Compile ---
    comp = compile_java(source_code)
    result.compilation = comp
    result.stages_completed.append(PipelineStage.COMPILE)

    if not comp.success:
        result.bugs.extend(analyze_compilation_errors(comp.errors))

        if use_llm:
            llm = LLMClient(llm_config)
            llm_resp = await llm.analyze_code(source_code, comp.errors)
            result.llm_analysis = llm_resp
            result.stages_completed.append(PipelineStage.ANALYZE)

            if llm_resp.success:
                fix_resp = await llm.suggest_fix(
                    source_code,
                    comp.errors,
                )
                if fix_resp.success:
                    result.fixed_code = fix_resp.content
                    result.stages_completed.append(PipelineStage.FIX)

        return result

    # --- Stage 2: Run ---
    exec_result = run_java(comp.class_name, comp.working_dir, stdin_input, timeout)
    result.execution = exec_result
    result.stages_completed.append(PipelineStage.RUN)

    if not exec_result.success:
        result.bugs.extend(analyze_runtime_errors(exec_result.stderr))

    # --- Stage 3: Output comparison ---
    if expected_output and exec_result.success:
        result.bugs.extend(analyze_output(expected_output, exec_result.stdout))

    # --- Stage 4: I/O test cases ---
    if test_cases:
        io_tests = generate_io_tests(source_code, test_cases)
        for tc in io_tests:
            _, tc_exec = compile_and_run(source_code, tc.input_value, timeout)
            tc_result = {
                "name": tc.name,
                "input": tc.input_value,
                "expected": tc.expected_output,
                "actual": tc_exec.stdout if tc_exec else "",
                "passed": (
                    tc_exec is not None
                    and tc_exec.success
                    and tc_exec.stdout.strip() == tc.expected_output.strip()
                ),
                "error": tc_exec.stderr if tc_exec and not tc_exec.success else "",
            }
            result.test_results.append(tc_result)
        result.stages_completed.append(PipelineStage.TEST)

    # --- Stage 5: LLM analysis ---
    if use_llm and result.bugs:
        llm = LLMClient(llm_config)
        error_text = "\n".join(b.message for b in result.bugs)
        llm_resp = await llm.analyze_code(source_code, error_text)
        result.llm_analysis = llm_resp
        result.stages_completed.append(PipelineStage.ANALYZE)

        if llm_resp.success:
            fix_resp = await llm.suggest_fix(source_code, error_text)
            if fix_resp.success:
                result.fixed_code = fix_resp.content
                result.stages_completed.append(PipelineStage.FIX)

    return result
