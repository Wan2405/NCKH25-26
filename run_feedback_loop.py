"""
run_feedback_loop.py
====================
CLI entry point for the AI-in-the-loop automated debugging pipeline.

Architecture
------------
run_feedback_loop.py
  └─ core/loop_orchestrator.py  (LoopOrchestrator)
       ├─ core/docker_manager.py    (DockerManager  – Python Docker SDK)
       ├─ execution/log_processor.py (LogProcessor)
       ├─ execution/error_classifier.py (ErrorClassifier)
       └─ llm/llm_client.py         (LLMClient – Ollama Llama 3.1)

Usage
-----
    python run_feedback_loop.py <problem_id> [options]

Options
-------
    --max-rounds N   Maximum number of fix iterations (default: 3).
    --workspace DIR  Path to the Maven project used as the sandbox
                     (default: workspace).
    --code FILE      Path to the initial Java source file.
                     Defaults to auto_grader/input_code/<class>.java
                     when omitted.

Example
-------
    python run_feedback_loop.py P001 --max-rounds 5
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

# ---------------------------------------------------------------------------
# Ensure top-level packages (core/, execution/, llm/) are importable when the
# script is run from any working directory.
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.docker_manager import DockerManager
from core.loop_orchestrator import LoopOrchestrator
from execution.log_processor import LogProcessor
from execution.error_classifier import ErrorClassifier
from llm.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Problem catalogue
# ---------------------------------------------------------------------------
PROBLEMS: dict[str, dict] = {
    "P001": {
        "title": "Tong hai so",
        "description": "Viet ham tinhTong(int a, int b) tra ve tong a + b",
        "class_name": "Solution",
        "default_code": "auto_grader/input_code/P001_TongHaiSo.java",
    },
    "P002": {
        "title": "Tinh giai thua",
        "description": "Viet ham tinhGiaiThua(int n) tra ve n!",
        "class_name": "Solution",
        "default_code": "auto_grader/input_code/P002_TinhGiaiThua.java",
    },
    "P003": {
        "title": "Kiem tra so nguyen to",
        "description": "Viet ham kiemTraNguyenTo(int n) tra ve true neu n la so nguyen to",
        "class_name": "Solution",
        "default_code": "auto_grader/input_code/P003_KiemTraNguyenTo.java",
    },
    "P004": {
        "title": "Tim max trong mang",
        "description": "Viet ham timMax(int[] arr) tra ve phan tu lon nhat",
        "class_name": "Solution",
        "default_code": "auto_grader/input_code/P004_TimMax.java",
    },
    "P005": {
        "title": "Dao nguoc chuoi",
        "description": "Viet ham daoNguoc(String s) tra ve chuoi dao nguoc",
        "class_name": "Solution",
        "default_code": "auto_grader/input_code/P005_DaoNguocChuoi.java",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_code(code_path: str) -> str:
    with open(code_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_class_name(code: str) -> str:
    m = re.search(r"public\s+class\s+(\w+)", code)
    return m.group(1) if m else "Solution"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AI-in-the-loop automated Java debugging pipeline (CLI)"
    )
    parser.add_argument("problem_id", help="Problem ID, e.g. P001")
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum fix iterations (default: 3)",
    )
    parser.add_argument(
        "--workspace",
        default="workspace",
        help="Path to Maven project workspace (default: workspace)",
    )
    parser.add_argument(
        "--code",
        default=None,
        help="Path to initial Java source file",
    )
    args = parser.parse_args(argv)

    problem_id = args.problem_id
    if problem_id not in PROBLEMS:
        print(f"[!] Unknown problem: {problem_id}")
        print("Available problems:")
        for pid, info in PROBLEMS.items():
            print(f"  {pid}: {info['title']}")
        return 1

    problem = PROBLEMS[problem_id]

    # Resolve initial code file
    code_path = args.code or problem.get("default_code", "")
    if not code_path or not os.path.exists(code_path):
        print(f"[!] Code file not found: {code_path!r}")
        return 1

    initial_code = _load_code(code_path)
    class_name = _extract_class_name(initial_code) or problem["class_name"]

    print("=" * 70)
    print("[*] NCKH25-26  AI-in-the-loop Automated Debugging Pipeline")
    print("=" * 70)
    print(f"Problem   : {problem_id} – {problem['title']}")
    print(f"Code file : {code_path}")
    print(f"Class name: {class_name}")
    print(f"Workspace : {args.workspace}")
    print(f"Max rounds: {args.max_rounds}")
    print("=" * 70)

    # Build pipeline components
    docker_manager = DockerManager()
    log_processor = LogProcessor()
    error_classifier = ErrorClassifier(use_llm=True)
    llm_client = LLMClient()

    orchestrator = LoopOrchestrator(
        docker_manager=docker_manager,
        log_processor=log_processor,
        error_classifier=error_classifier,
        llm_client=llm_client,
        workspace_path=args.workspace,
        max_rounds=args.max_rounds,
    )

    result = orchestrator.run(
        problem_id=problem_id,
        initial_code=initial_code,
        problem_description=problem["description"],
        class_name=class_name,
    )

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    status = "PASSED" if result["success"] else "FAILED"
    print(f"Status    : {status}")
    print(f"Rounds    : {result['rounds']}")
    for h in result["history"]:
        tag = "✅" if h["status"] == "PASSED" else "❌"
        print(f"  Round {h['round']}: {h['error_type']} {tag}")
    print("=" * 70)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
