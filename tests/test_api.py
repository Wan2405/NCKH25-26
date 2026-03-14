"""
Tests for the REST API endpoints.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)

GOOD_CODE = """\
public class Good {
    public static void main(String[] args) {
        System.out.println("hi");
    }
}
"""

BAD_CODE = """\
public class Bad {
    public static void main(String[] args) {
        int x = 1
    }
}
"""


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_compile_success():
    resp = client.post("/compile", json={"source_code": GOOD_CODE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["class_name"] == "Good"
    assert data["errors"] == []


def test_compile_failure():
    resp = client.post("/compile", json={"source_code": BAD_CODE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert len(data["errors"]) > 0


def test_run_success():
    resp = client.post("/run", json={"source_code": GOOD_CODE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["compile_success"] is True
    assert data["run_success"] is True
    assert "hi" in data["stdout"]


def test_run_compile_failure():
    resp = client.post("/run", json={"source_code": BAD_CODE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["compile_success"] is False
    assert data["run_success"] is False


def test_generate_tests():
    resp = client.post("/generate-tests", json={"source_code": GOOD_CODE, "use_llm": False})
    assert resp.status_code == 200
    data = resp.json()
    assert "GoodTest" in data["test_source"]


def test_pipeline_success():
    resp = client.post("/pipeline", json={"source_code": GOOD_CODE, "max_iterations": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["fixed"] is True
    assert data["total_iterations"] == 1


def test_pipeline_failure():
    resp = client.post("/pipeline", json={"source_code": BAD_CODE, "max_iterations": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["fixed"] is False
    assert len(data["iterations"]) > 0
    assert data["iterations"][0]["compile_success"] is False
