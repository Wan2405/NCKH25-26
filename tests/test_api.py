"""Tests for the FastAPI REST API."""

import pytest
from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


class TestHealthCheck:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCompileEndpoint:
    def test_valid_code(self):
        response = client.post(
            "/compile",
            json={"source_code": 'public class APIHello { public static void main(String[] args) { System.out.println("Hi"); } }'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["class_name"] == "APIHello"

    def test_invalid_code(self):
        response = client.post(
            "/compile",
            json={"source_code": "public class APIBad { invalid }"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["errors"] != ""


class TestRunEndpoint:
    def test_run_valid(self):
        response = client.post(
            "/run",
            json={
                "source_code": 'public class APIRun { public static void main(String[] args) { System.out.println("OK"); } }'
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["compilation_success"] is True
        assert data["execution_success"] is True
        assert "OK" in data["stdout"]

    def test_run_compile_error(self):
        response = client.post(
            "/run",
            json={"source_code": "public class APIRunBad { invalid }"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["compilation_success"] is False


class TestAnalyzeEndpoint:
    def test_analyze_compilation_error(self):
        response = client.post(
            "/analyze",
            json={
                "source_code": "x",
                "error_output": "Main.java:3: error: ';' expected\n        int x = 10\n",
                "error_type": "compilation",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["bugs"]) > 0

    def test_analyze_runtime_error(self):
        response = client.post(
            "/analyze",
            json={
                "source_code": "x",
                "error_output": 'Exception in thread "main" java.lang.NullPointerException\n\tat Main.main(Main.java:5)\n',
                "error_type": "runtime",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["bugs"]) > 0
        assert "NullPointerException" in data["bugs"][0]["message"]


class TestGenerateTestsEndpoint:
    def test_generate(self):
        source = (
            "public class APICalc {\n"
            "  public static int add(int a, int b) { return a + b; }\n"
            "}"
        )
        response = client.post(
            "/generate-tests",
            json={"source_code": source},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["test_class_name"] == "APICalcTest"
        assert data["test_count"] > 0
        assert "@Test" in data["test_source_code"]


class TestPipelineEndpoint:
    def test_pipeline_success(self):
        response = client.post(
            "/pipeline",
            json={
                "source_code": 'public class APIPipe { public static void main(String[] args) { System.out.println("hi"); } }',
                "expected_output": "hi",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["compilation_success"] is True
        assert data["execution_success"] is True
        assert len(data["bugs"]) == 0
