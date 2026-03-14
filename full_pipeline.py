from auto_grader.modules.code_generator import CodeGenerator
from auto_grader.modules.feedback_generator import FeedbackGenerator
from auto_grader.modules.log_processor import LogProcessor
from auto_grader.modules.error_classifier import ErrorClassifier
from auto_grader.docker.run_in_docker import DockerRunner

import shutil, os

def fix_until_pass(problem_id, problem_desc, code0, max_rounds=3):
    code = code0
    docker_runner = DockerRunner()
    feedback_gen = FeedbackGenerator()
    processor = LogProcessor()
    classifier = ErrorClassifier()

    for round in range(1, max_rounds+1):
        print(f"\n🟡 ROUND {round}/{max_rounds}")
        # 1. Save code vào Maven project
        code_path = f"auto_grader/maven_project/src/main/java/com/example/{problem_id}_Solution.java"
        os.makedirs(os.path.dirname(code_path), exist_ok=True)
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)
        # 2. Test qua Docker
        output = docker_runner.run_test("auto_grader/maven_project")
        # 3. Log JSON
        with open("auto_grader/grading_history.txt", "w", encoding="utf-8") as f:
            f.write(output)
        log_json = processor.process_log("auto_grader/grading_history.txt", "SV001", problem_id)
        error_result = classifier.classify(log_json)
        if error_result["loai_loi"] == "PASSED":
            print(f"💚 PASSED after {round} round(s)!")
            return code
        # 4. Feedback LLM
        reply = feedback_gen.generate_fix_suggestion(code, error_result, problem_desc)
        code = reply.get("fixed_code", code)  # Nếu không fix được thì break
        if code is None: break
    print(f"❌ Không pass sau {max_rounds} vòng.")
    return None

# --- DEMO: auto fix P001 ---
if __name__ == "__main__":
    problem_id = "P001"
    problem_desc = "Viet ham tinhTong(int a, int b) tra ve tong a + b"
    # B1: Tự sinh code - hoặc lấy code từ file, từ code_generator
    with open("auto_grader/input_code/P001_TongHaiSo.java", "r", encoding="utf-8") as f:
        initial_code = f.read()
    # Auto-fix loop
    fix_until_pass(problem_id, problem_desc, initial_code, max_rounds=3)