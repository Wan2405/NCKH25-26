"""
API route definitions.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.bug_analyzer.analyzer import analyze_compilation, analyze_runtime
from src.java_executor.compiler import compile_java
from src.java_executor.runner import run_java
from src.llm_client.client import LLMClient
from src.pipeline.pipeline import run_pipeline
from src.test_generator.generator import generate_tests

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class CompileRequest(BaseModel):
    source_code: str = Field(..., description="Java source code to compile")


class CompileResponse(BaseModel):
    success: bool
    class_name: str
    errors: List[dict]
    warnings: List[dict]
    raw_output: str


class RunRequest(BaseModel):
    source_code: str = Field(..., description="Java source code to compile and run")
    stdin: Optional[str] = Field(None, description="Optional standard input")


class RunResponse(BaseModel):
    compile_success: bool
    run_success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    has_exception: bool
    compile_errors: List[dict]


class PipelineRequest(BaseModel):
    source_code: str = Field(..., description="Java source code to process")
    stdin: Optional[str] = Field(None, description="Optional stdin for program execution")
    max_iterations: Optional[int] = Field(None, description="Max LLM fix iterations (default: 3)")
    generate_unit_tests: bool = Field(True, description="Whether to generate JUnit 5 tests")


class BugInfo(BaseModel):
    kind: str
    description: str
    line: int
    suggestion: str


class IterationInfo(BaseModel):
    iteration: int
    source_code: str
    compile_success: bool
    run_success: Optional[bool]
    bugs: List[BugInfo]
    bug_summary: str


class PipelineResponse(BaseModel):
    fixed: bool
    total_iterations: int
    original_code: str
    final_code: str
    generated_tests: str
    iterations: List[IterationInfo]
    summary: str


class GenerateTestsRequest(BaseModel):
    source_code: str = Field(..., description="Java source code to generate tests for")
    use_llm: bool = Field(True, description="Whether to use LLM for test generation")


class GenerateTestsResponse(BaseModel):
    test_source: str


class ExplainRequest(BaseModel):
    source_code: str


class ExplainResponse(BaseModel):
    explanation: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/compile", response_model=CompileResponse)
def compile_endpoint(request: CompileRequest):
    """Compile Java source code and return diagnostics."""
    result = compile_java(request.source_code)
    return CompileResponse(
        success=result.success,
        class_name=result.class_name,
        errors=[
            {"line": d.line, "column": d.column, "message": d.message, "excerpt": d.source_excerpt}
            for d in result.errors
        ],
        warnings=[
            {"line": d.line, "column": d.column, "message": d.message, "excerpt": d.source_excerpt}
            for d in result.warnings
        ],
        raw_output=result.raw_output,
    )


@router.post("/run", response_model=RunResponse)
def run_endpoint(request: RunRequest):
    """Compile and run Java source code."""
    compilation = compile_java(request.source_code)

    if not compilation.success:
        return RunResponse(
            compile_success=False,
            run_success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            execution_time_ms=0.0,
            has_exception=False,
            compile_errors=[
                {"line": d.line, "message": d.message, "suggestion": _hint_for(d.message)}
                for d in compilation.errors
            ],
        )

    run = run_java(compilation, stdin=request.stdin)
    return RunResponse(
        compile_success=True,
        run_success=run.success,
        stdout=run.stdout,
        stderr=run.stderr,
        exit_code=run.exit_code,
        execution_time_ms=run.execution_time_ms,
        has_exception=run.has_exception,
        compile_errors=[],
    )


@router.post("/pipeline", response_model=PipelineResponse)
def pipeline_endpoint(request: PipelineRequest):
    """
    Run the full automated testing & debugging pipeline.

    Compiles, runs, analyses, auto-fixes (with LLM if configured), and
    generates unit tests for the submitted Java code.
    """
    kwargs = {}
    if request.max_iterations is not None:
        kwargs["max_iterations"] = request.max_iterations

    result = run_pipeline(
        request.source_code,
        stdin=request.stdin,
        generate_unit_tests=request.generate_unit_tests,
        **kwargs,
    )

    iterations = [
        IterationInfo(
            iteration=rec.iteration,
            source_code=rec.source_code,
            compile_success=rec.compilation.success,
            run_success=rec.run.success if rec.run else None,
            bugs=[
                BugInfo(
                    kind=b.kind,
                    description=b.description,
                    line=b.line,
                    suggestion=b.suggestion,
                )
                for b in rec.bug_report.bugs
            ],
            bug_summary=rec.bug_report.summary,
        )
        for rec in result.iterations
    ]

    return PipelineResponse(
        fixed=result.fixed,
        total_iterations=result.total_iterations,
        original_code=result.original_code,
        final_code=result.final_code,
        generated_tests=result.generated_tests,
        iterations=iterations,
        summary=result.summary(),
    )


@router.post("/generate-tests", response_model=GenerateTestsResponse)
def generate_tests_endpoint(request: GenerateTestsRequest):
    """Generate a JUnit 5 test class for the given Java code."""
    llm = LLMClient() if request.use_llm else None
    test_source = generate_tests(request.source_code, llm, use_llm=request.use_llm)
    return GenerateTestsResponse(test_source=test_source)


@router.post("/explain", response_model=ExplainResponse)
def explain_endpoint(request: ExplainRequest):
    """Ask the LLM to explain the given Java code."""
    llm = LLMClient()
    explanation = llm.explain_code(request.source_code)
    return ExplainResponse(explanation=explanation)


# ── private helpers ───────────────────────────────────────────────────────────

def _hint_for(message: str) -> str:
    """Reuse the bug analyzer hint lookup without importing internals."""
    from src.bug_analyzer.analyzer import _COMPILE_HINTS, _hint
    return _hint(_COMPILE_HINTS, message)
