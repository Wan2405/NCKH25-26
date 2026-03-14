"""Tests for the pipeline module."""

import pytest

from src.pipeline import PipelineStage, run_pipeline


@pytest.mark.asyncio
class TestPipeline:
    async def test_successful_pipeline(self):
        code = (
            'public class PipeOK {\n'
            '  public static void main(String[] args) {\n'
            '    System.out.println("hello");\n'
            '  }\n'
            '}'
        )
        result = await run_pipeline(code, expected_output="hello")
        assert result.compilation is not None
        assert result.compilation.success is True
        assert result.execution is not None
        assert result.execution.success is True
        assert PipelineStage.COMPILE in result.stages_completed
        assert PipelineStage.RUN in result.stages_completed
        assert len(result.bugs) == 0

    async def test_compilation_failure_pipeline(self):
        code = "public class PipeBad { invalid }"
        result = await run_pipeline(code)
        assert result.compilation is not None
        assert result.compilation.success is False
        assert result.execution is None
        assert len(result.bugs) > 0

    async def test_runtime_error_pipeline(self):
        code = (
            "public class PipeRT {\n"
            "  public static void main(String[] args) {\n"
            "    int x = 1 / 0;\n"
            "  }\n"
            "}"
        )
        result = await run_pipeline(code)
        assert result.compilation.success is True
        assert result.execution is not None
        assert result.execution.success is False
        assert len(result.bugs) > 0

    async def test_output_mismatch(self):
        code = (
            'public class PipeMis {\n'
            '  public static void main(String[] args) {\n'
            '    System.out.println("wrong");\n'
            '  }\n'
            '}'
        )
        result = await run_pipeline(code, expected_output="correct")
        assert len(result.bugs) > 0
        assert any(b.message and "mismatch" in b.message.lower() for b in result.bugs)

    async def test_io_test_cases(self):
        code = (
            "import java.util.Scanner;\n"
            "public class PipeIO {\n"
            "  public static void main(String[] args) {\n"
            "    Scanner s = new Scanner(System.in);\n"
            "    int n = s.nextInt();\n"
            "    System.out.println(n * 2);\n"
            "    s.close();\n"
            "  }\n"
            "}"
        )
        test_cases = [
            {"input": "5\n", "expected_output": "10"},
            {"input": "0\n", "expected_output": "0"},
        ]
        result = await run_pipeline(code, test_cases=test_cases)
        assert PipelineStage.TEST in result.stages_completed
        assert len(result.test_results) == 2
        assert result.test_results[0]["passed"] is True
        assert result.test_results[1]["passed"] is True
