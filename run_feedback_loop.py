"""
run_feedback_loop.py

Mục đích:
    File chính để chạy hệ thống gỡ lỗi Java tự động.
    Đây là nơi bắt đầu khi chạy lệnh: python run_feedback_loop.py

Cách hoạt động:
    1. Đọc file Java từ thư mục workspace
    2. Khởi tạo các module: Docker, LogProcessor, ErrorClassifier, LLM
    3. Chạy vòng lặp sửa lỗi qua LoopOrchestrator

Cách sử dụng:
    python run_feedback_loop.py --workspace ./workspace --max-rounds 3

    --workspace: thư mục chứa code Java cần sửa (bắt buộc)
    --max-rounds: số vòng sửa lỗi tối đa, mặc định là 3
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

# Thêm thư mục gốc vào sys.path để có thể import các module (core/, execution/, llm/)
# dù chạy script từ thư mục nào
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


# === Các hàm hỗ trợ ===

def _find_java_source(workspace: str) -> str | None:
    """Tìm file .java đầu tiên trong thư mục src/main/java/ của workspace."""
    src_root = os.path.join(workspace, "src", "main", "java")
    if not os.path.isdir(src_root):
        return None
    for dirpath, _, filenames in os.walk(src_root):
        for fname in filenames:
            if fname.endswith(".java"):
                return os.path.join(dirpath, fname)
    return None


def _load_code(code_path: str) -> str:
    with open(code_path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_class_name(code: str) -> str:
    m = re.search(r"public\s+class\s+(\w+)", code)
    return m.group(1) if m else "Solution"


# === Hàm main - điểm bắt đầu chính ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AI-in-the-loop automated Java debugging pipeline (CLI)"
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help=(
            "Path to the Maven project workspace containing the corrupted "
            "Java source file and pom.xml"
        ),
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum fix iterations (default: 3)",
    )
    args = parser.parse_args(argv)

    workspace = args.workspace

    if not os.path.isdir(workspace):
        print(f"[!] Workspace directory not found: {workspace!r}")
        return 1

    # Locate the Java source file inside the workspace
    code_path = _find_java_source(workspace)
    if not code_path:
        print(
            f"[!] No .java file found under {workspace}/src/main/java/. "
            "Please ensure the workspace contains your Java source."
        )
        return 1

    initial_code = _load_code(code_path)
    class_name = _extract_class_name(initial_code)

    print("=" * 70)
    print("[*] NCKH25-26  AI-in-the-loop Automated Debugging Pipeline")
    print("=" * 70)
    print(f"Workspace : {workspace}")
    print(f"Code file : {code_path}")
    print(f"Class name: {class_name}")
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
        workspace_path=workspace,
        max_rounds=args.max_rounds,
    )

    result = orchestrator.run(
        initial_code=initial_code,
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
