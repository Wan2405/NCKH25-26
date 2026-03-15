"""
auto_fixer.py

Mục đích:
    Vòng lặp tự động sửa code Java cho đến khi pass tất cả test.
    Kết hợp LogProcessor + ErrorClassifier + FeedbackGenerator.

Cách hoạt động:
    1. Lưu code vào Maven project
    2. Chạy test qua Docker
    3. Phân tích kết quả
    4. Nếu FAILED → Gọi LLM sửa → Lặp lại
    5. Nếu PASSED hoặc hết số vòng → Dừng

Lưu ý:
    - Chạy test qua Docker để đảm bảo an toàn
    - Lịch sử các vòng được lưu ra file JSON
"""

import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path

# Thêm thư mục gốc vào sys.path để import được llm package
_ROOT = str(Path(__file__).parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Import các module cần thiết (dùng relative import)
from .log_processor import LogProcessor
from .error_classifier import ErrorClassifier
from .feedback_generator import FeedbackGenerator

from llm.code_sanitizer import sanitize_java_code


class AutoFixer:
    """
    Tự động sửa code Java qua nhiều vòng lặp.
    
    Tham số:
        max_iterations: Số vòng tối đa (tránh loop vô hạn)
    """
    
    def __init__(self, max_iterations=5):
        self.max_iterations = max_iterations

        # Khởi tạo các module xử lý
        self.log_processor = LogProcessor()
        self.error_classifier = ErrorClassifier(use_llm=True)
        self.feedback_gen = FeedbackGenerator()

        # Đường dẫn Maven project và output
        self.maven_project = Path("auto_grader/maven_project")
        self.output_dir = Path("auto_grader/output/auto_fix_history")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fix_until_pass(self, problem_id, initial_code, problem_description, class_name=None):
        """
        Vòng lặp chính: Sửa code cho đến khi pass hoặc hết số vòng.
        
        Tham số:
            problem_id: ID bài tập
            initial_code: Code ban đầu của sinh viên
            problem_description: Đề bài
            class_name: Tên class (tự động tìm nếu không đặt)
        
        Trả về:
            Dict chứa success, iterations, final_code, history
        """

        # Tự động tìm tên class nếu không được chỉ định
        if class_name is None:
            class_name = self._extract_class_name(initial_code, problem_id)

        current_code = initial_code
        history = []
        classification = {"loai_loi": "Unknown"}

        print("\n" + "=" * 70)
        print("BẮT ĐẦU AUTO-FIX LOOP")
        print("=" * 70)

        for iteration in range(1, self.max_iterations + 1):
            print("\n[ITERATION {}/{}]".format(iteration, self.max_iterations))
            print("-" * 70)

            # Bước 1: Lưu code vào Maven project
            self._save_to_maven_project(class_name, current_code)

            # Bước 2: Chạy test qua Docker
            test_log = self._run_maven_test()

            # Bước 3: Xử lý và phân tích log
            log_data = self._process_log(problem_id, iteration)
            classification = self.error_classifier.classify(log_data)

            # Bước 4: Lưu lịch sử vòng này
            iteration_data = {
                "iteration": iteration,
                "code": current_code,
                "error_type": classification["loai_loi"],
                "error_reason": classification["nguyen_nhan"],
                "test_results": log_data.get("test_results", {}),
                "timestamp": datetime.now().isoformat(),
            }
            history.append(iteration_data)

            # Bước 5: Kiểm tra kết quả
            if classification["loai_loi"] == "PASSED":
                print("\nCODE ĐÃ PASS SAU {} LẦN!".format(iteration))
                return {
                    "success": True,
                    "iterations": iteration,
                    "final_code": current_code,
                    "history": history,
                    "problem_id": problem_id,
                }

            # Bước 6: Nếu chưa pass và còn vòng → Gọi LLM sửa
            print("Test failed: {}".format(classification["loai_loi"]))
            print("Nguyên nhân: {}...".format(str(classification["nguyen_nhan"])[:100]))

            if iteration < self.max_iterations:
                print("Đang gọi LLM sửa code...")

                feedback = self.feedback_gen.generate_fix_suggestion(
                    current_code, classification, problem_description
                )

                if feedback.get("fixed_code", "").strip():
                    current_code = sanitize_java_code(
                        feedback["fixed_code"], expected_class=class_name
                    )
                    iteration_data["fixed_code"] = current_code
                    iteration_data["fix_explanation"] = feedback.get("explanation", "")
                    print("LLM đã đề xuất code mới")
                else:
                    print("LLM không sinh được code sửa")
                    break

        # Hết số lần thử
        print("\nKHÔNG THỂ SỬA SAU {} LẦN".format(self.max_iterations))
        return {
            "success": False,
            "iterations": self.max_iterations,
            "final_code": current_code,
            "last_error": classification.get("loai_loi", "Unknown"),
            "history": history,
            "problem_id": problem_id,
        }

    def _extract_class_name(self, code, problem_id):
        """Tự động tìm tên class từ code (hoặc dùng problem_id nếu không tìm được)."""
        match = re.search(r"public\s+class\s+(\w+)", code)
        if match:
            return match.group(1)
        return "{}_Solution".format(problem_id)

    def _save_to_maven_project(self, class_name, code):
        """Lưu code vào đúng vị trí trong Maven project."""
        dest = (
            self.maven_project
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / "{}.java".format(class_name)
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(code)

    def _run_maven_test(self):
        """Chạy Maven test qua Docker container và lưu log."""
        from auto_grader.docker.run_in_docker import get_docker_runner

        runner = get_docker_runner()
        output = runner.run_test(str(self.maven_project))

        # Lưu log ra file để module khác có thể đọc
        log_file = Path("auto_grader/grading_history.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(output)

        return output

    def _process_log(self, problem_id, iteration):
        """Xử lý log test vừa chạy."""
        log_data = self.log_processor.process_log(
            log_path="auto_grader/grading_history.txt",
            student_id="AUTO_FIX_IT{}".format(iteration),
            problem_id=problem_id,
        )
        return log_data

    def save_history(self, fix_result):
        """Lưu toàn bộ lịch sử sửa lỗi ra file JSON."""
        problem_id = fix_result["problem_id"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = "{}_autofix_{}.json".format(problem_id, timestamp)
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(fix_result, f, indent=2, ensure_ascii=False)

        print("\nĐã lưu lịch sử: {}".format(filepath))
        return str(filepath)
