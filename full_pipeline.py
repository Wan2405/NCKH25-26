"""
FULL PIPELINE
=============
Demonstration of the complete auto-fix pipeline.

Uses DockerRunner (via the Python Docker SDK) to compile and test Java code
inside a sandboxed container, then calls the LLM to fix any errors.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_grader.modules.code_generator import CodeGenerator
from auto_grader.modules.feedback_generator import FeedbackGenerator
from auto_grader.modules.log_processor import LogProcessor
from auto_grader.modules.error_classifier import ErrorClassifier
from auto_grader.docker.run_in_docker import DockerRunner
from llm.code_sanitizer import sanitize_java_code

# Mapping problem_id → Java class name (compatible with runner convention)
PROBLEM_CLASS_MAP = {
    "P001": "P001_TongHaiSo",
    "P002": "P002_TinhGiaiThua",
    "P003": "P003_KiemTraNguyenTo",
    "P004": "P004_TimMax",
    "P005": "P005_DaoNguocChuoi",
}


def fix_until_pass(problem_id, problem_desc, code0, max_rounds=3):
    code = code0
    docker_runner = DockerRunner()
    feedback_gen = FeedbackGenerator()
    processor = LogProcessor()
    classifier = ErrorClassifier()

    # Lấy tên class đúng từ mapping
    target_class = PROBLEM_CLASS_MAP.get(problem_id, "{}_Solution".format(problem_id))

    for round_num in range(1, max_rounds + 1):
        print("\n🟡 ROUND {}/{}".format(round_num, max_rounds))

        # 1. Sửa tên class trong code
        class_match = re.search(r"public\s+class\s+(\w+)", code)
        if class_match:
            old_class = class_match.group(1)
            if old_class != target_class:
                code = code.replace(
                    "public class {}".format(old_class),
                    "public class {}".format(target_class),
                )

        # 2. Save code vào Maven project
        code_path = os.path.join(
            "auto_grader",
            "maven_project",
            "src",
            "main",
            "java",
            "com",
            "example",
            "{}.java".format(target_class),
        )
        os.makedirs(os.path.dirname(code_path), exist_ok=True)
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)

        # 3. Test qua Docker (Python Docker SDK)
        output = docker_runner.run_test("auto_grader/maven_project")

        # 4. Log JSON
        with open("auto_grader/grading_history.txt", "w", encoding="utf-8") as f:
            f.write(output)
        log_json = processor.process_log(
            "auto_grader/grading_history.txt", "SV001", problem_id
        )
        error_result = classifier.classify(log_json)

        if error_result["loai_loi"] == "PASSED":
            print("💚 PASSED after {} round(s)!".format(round_num))
            return code

        # 5. Feedback LLM
        reply = feedback_gen.generate_fix_suggestion(code, error_result, problem_desc)
        fixed_code = reply.get("fixed_code")
        if not fixed_code or not fixed_code.strip():
            print("❌ LLM không sinh được code sửa")
            break
        code = sanitize_java_code(fixed_code, expected_class=target_class)

    print("❌ Không pass sau {} vòng.".format(max_rounds))
    return None


# --- DEMO: auto fix P001 ---
if __name__ == "__main__":
    problem_id = "P001"
    problem_desc = "Viet ham tinhTong(int a, int b) tra ve tong a + b"

    input_file = "auto_grader/input_code/P001_TongHaiSo.java"
    if not os.path.exists(input_file):
        print("❌ File không tồn tại: {}".format(input_file))
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        initial_code = f.read()

    fix_until_pass(problem_id, problem_desc, initial_code, max_rounds=3)
