"""
loop_orchestrator.py

Mục đích:
    Điều khiển vòng lặp chính của hệ thống sửa lỗi tự động.
    Đây là "bộ não" quyết định khi nào dừng, khi nào gọi LLM sửa code.

Cách hoạt động (mỗi vòng):
    1. Ghi code Java vào workspace
    2. Gọi DockerManager để compile và chạy test
    3. Dùng LogProcessor phân tích log
    4. Dùng ErrorClassifier xác định loại lỗi
    5. Nếu PASSED → dừng và trả về thành công
    6. Nếu FAILED → gọi LLM sinh code sửa → tiếp tục vòng mới

Vòng lặp dừng khi:
    - Code pass tất cả test
    - Hết số vòng tối đa (max_rounds)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from llm.code_sanitizer import sanitize_java_code

if TYPE_CHECKING:
    from core.docker_manager import DockerManager
    from execution.log_processor import LogProcessor
    from execution.error_classifier import ErrorClassifier
    from llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class LoopOrchestrator:
    """
    Điều khiển vòng lặp sửa lỗi.
    
    Tham số:
        docker_manager: Quản lý Docker để chạy test
        log_processor: Phân tích log Maven
        error_classifier: Phân loại lỗi
        llm_client: Gọi LLM để sinh code sửa
        workspace_path: Thư mục chứa project Maven
        max_rounds: Số vòng sửa lỗi tối đa
    """

    def __init__(
        self,
        docker_manager: "DockerManager",
        log_processor: "LogProcessor",
        error_classifier: "ErrorClassifier",
        llm_client: "LLMClient",
        workspace_path: str = "workspace",
        max_rounds: int = 3,
        history_dir: str = "auto_grader/output/auto_fix_history",
    ) -> None:
        self.docker_manager = docker_manager
        self.log_processor = log_processor
        self.error_classifier = error_classifier
        self.llm_client = llm_client
        self.workspace_path = workspace_path
        self.max_rounds = max_rounds
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    # === Hàm công khai ===

    def run(
        self,
        initial_code: str,
        class_name: str = "Solution",
        problem_description: str = "",
        student_id: str = "SV001",
    ) -> dict:
        """
        Chạy vòng lặp sửa lỗi.
        
        Trả về dict chứa:
            success: True/False - code có pass không
            rounds: Số vòng đã chạy
            final_code: Code cuối cùng
            history: Lịch sử từng vòng
        """
        current_code = initial_code
        history: list[dict] = []

        print("=" * 70)
        print("[*] FEEDBACK LOOP START")
        print("=" * 70)

        for round_num in range(1, self.max_rounds + 1):
            print(f"\n[Round {round_num}/{self.max_rounds}]")
            print("-" * 70)

            # 1. Write code to workspace
            self._save_code(class_name, current_code)
            print(f"[*] Code saved → {class_name}.java")

            # 2. Compile + test via Docker
            print("[*] Running tests via Docker …")
            raw_log = self.docker_manager.compile_and_test(self.workspace_path)

            # 3. Parse log
            log_data = self.log_processor.process(raw_log, student_id)

            # 4. Classify
            classification = self.error_classifier.classify(log_data)
            error_type = classification.get("loai_loi", "Unknown")
            reason = classification.get("nguyen_nhan", "")

            history.append(
                {
                    "round": round_num,
                    "error_type": error_type,
                    "reason": str(reason)[:200],
                    "status": "PASSED" if error_type == "PASSED" else "FAILED",
                    "timestamp": datetime.now().isoformat(),
                }
            )

            print(f"[*] Result: {error_type}")

            if error_type == "PASSED":
                print(f"\n[+] PASSED after {round_num} round(s)!")
                return self._build_result(
                    success=True,
                    history=history,
                    final_code=current_code,
                )

            if round_num == self.max_rounds:
                break

            # 5. Ask LLM for a fix
            print("[*] Requesting fix from LLM …")
            suggestion = self.llm_client.generate_fix(
                current_code, classification, problem_description
            )
            fixed_code = suggestion.get("fixed_code", "")
            if not fixed_code.strip():
                print("[!] LLM returned no fix")
                history[-1]["status"] = "FAILED_TO_FIX"
                break

            fixed_code = sanitize_java_code(fixed_code, expected_class=class_name)
            current_code = fixed_code
            print("[+] Code updated from LLM suggestion")

        print("\n[*] FEEDBACK LOOP END")
        return self._build_result(
            success=False,
            history=history,
            final_code=current_code,
        )

    # === Các hàm nội bộ ===

    def _save_code(self, class_name: str, code: str) -> None:
        dest = (
            Path(self.workspace_path)
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / f"{class_name}.java"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding="utf-8")

    def _build_result(
        self,
        success: bool,
        history: list[dict],
        final_code: str,
    ) -> dict:
        result = {
            "success": success,
            "rounds": len(history),
            "final_code": final_code,
            "history": history,
        }
        self._persist_history(result)
        return result

    def _persist_history(self, result: dict) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = self.history_dir / f"loop_{ts}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[+] History saved → {out}")
