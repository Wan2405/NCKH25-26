"""
LOOP ORCHESTRATOR
=================
Controls the AI-in-the-loop automated debugging feedback loop.

Flow for each round:
    1. Write the current Java code to the workspace Maven project.
    2. Call DockerManager to compile and run JUnit tests.
    3. Parse the raw log with LogProcessor.
    4. Classify the error with ErrorClassifier.
    5. If PASSED → stop and return success.
    6. Otherwise call LLMClient for a fix → update code → repeat.

The loop stops when the code passes all tests or the maximum number of
rounds is exhausted.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.docker_manager import DockerManager
    from execution.log_processor import LogProcessor
    from execution.error_classifier import ErrorClassifier
    from llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class LoopOrchestrator:
    """
    Args:
        docker_manager:   A :class:`~core.docker_manager.DockerManager` instance.
        log_processor:    Parses raw Maven output into a structured dict.
        error_classifier: Classifies the parsed log.
        llm_client:       Generates code fixes via an LLM.
        workspace_path:   Root of the Maven project used as the sandbox.
        max_rounds:       Hard stop after this many iterations.
        history_dir:      Directory for persisting loop history JSON files.
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

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        problem_id: str,
        initial_code: str,
        problem_description: str,
        class_name: str = "Solution",
        student_id: str = "SV001",
    ) -> dict:
        """
        Execute the debugging loop.

        Returns a result dict::

            {
                "success":    bool,
                "rounds":     int,
                "final_code": str,
                "history":    list[dict],
                "problem_id": str,
            }
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
            log_data = self.log_processor.process(raw_log, student_id, problem_id)

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
                    problem_id=problem_id,
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

            current_code = fixed_code
            print("[+] Code updated from LLM suggestion")

        print("\n[*] FEEDBACK LOOP END")
        return self._build_result(
            success=False,
            history=history,
            final_code=current_code,
            problem_id=problem_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
        problem_id: str,
    ) -> dict:
        result = {
            "success": success,
            "rounds": len(history),
            "final_code": final_code,
            "history": history,
            "problem_id": problem_id,
        }
        self._persist_history(problem_id, result)
        return result

    def _persist_history(self, problem_id: str, result: dict) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = self.history_dir / f"{problem_id}_loop_{ts}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[+] History saved → {out}")
