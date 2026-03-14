"""
AUTO GRADER RUNNER - Dynamic + Docker
"""

import os
import shutil
import subprocess
import sys
import re

sys.path.insert(0, os.path.dirname(__file__))
from auto_grader.modules.log_processor import LogProcessor

# Mapping problem_id → tên class Java tương ứng với test
PROBLEM_CLASS_MAP = {
    'P001': 'P001_TongHaiSo',
    'P002': 'P002_TinhGiaiThua',
    'P003': 'P003_KiemTraNguyenTo',
    'P004': 'P004_TimMax',
    'P005': 'P005_DaoNguocChuoi',
}

def main():
    # Nhận tham số từ CLI
    if len(sys.argv) < 3:
        print("Cách dùng: python runner.py P001 code_file.java [student_id]")
        sys.exit(1)
    
    problem_id = sys.argv[1]
    code_file = sys.argv[2]
    student_id = sys.argv[3] if len(sys.argv) > 3 else "SV001"
    
    print("=" * 60)
    print("🤖 AUTO GRADER - RUNNER")
    print("=" * 60)
    print(f"Problem ID: {problem_id}")
    print(f"Code file: {code_file}")
    print(f"Student ID: {student_id}")
    
    # Kiểm tra file code
    if not os.path.exists(code_file):
        print(f"❌ File không tồn tại: {code_file}")
        return
    
    # Tính toán đường dẫn - lấy tên class từ mapping
    target_class = PROBLEM_CLASS_MAP.get(problem_id, f"{problem_id}_Solution")
    java_filename = f"{target_class}.java"
    maven_root = os.path.join("auto_grader", "maven_project")
    dest_path = os.path.join(
        maven_root, 
        "src", "main", "java", "com", "example", 
        java_filename
    )
    log_file = os.path.join("auto_grader", "grading_history.txt")
    
    # Đọc code
    print("\n[*] Đang đọc code...")
    with open(code_file, 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    # Sửa tên lớp
    print("[*] Đang sửa tên lớp...")
    class_match = re.search(r'public\s+class\s+(\w+)', code_content)
    
    if class_match:
        old_class = class_match.group(1)
        new_class = target_class
        code_content = code_content.replace(
            f"public class {old_class}",
            f"public class {new_class}"
        )
        print(f"  ✅ Đổi: {old_class} → {new_class}")
    
    # Copy code
    print("[*] Đang copy code...")
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write(code_content)
        print(f"  ✅ Copy xong: {dest_path}")
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")
        return
    
    # Chạy Maven test
    print("\n[*] Đang chạy Maven test...")
    mvn_cmd = "mvn.cmd" if os.name == 'nt' else "mvn"
    
    try:
        result = subprocess.run(
            [mvn_cmd, "clean", "test"],
            cwd=maven_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=120
        )
        
        full_log = result.stdout
        if result.stderr:
            full_log += "\n--- ERROR STREAM ---\n" + result.stderr
        full_log += f"\n--- EXIT CODE: {result.returncode} ---"
        
    except Exception as e:
        full_log = f"ERROR: {str(e)}"
    
    # Ghi log
    print("[*] Đang ghi log...")
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(full_log)
    print(f"  ✅ Log: {log_file}")
    
    # Xử lý JSON
    print("[*] Đang xử lý JSON...")
    processor = LogProcessor()
    structured_data = processor.process_log(
        log_path=log_file,
        student_id=student_id,
        problem_id=problem_id
    )
    
    json_file = processor.save_json(structured_data)
    print(f"  ✅ JSON: {json_file}")
    
    # Tóm tắt
    print("\n" + "=" * 60)
    execution = structured_data.get('execution', {})
    test_results = structured_data.get('test_results', {})
    
    print(f"Loại lỗi: {execution.get('error_type', 'N/A')}")
    print(f"Exit code: {execution.get('exit_code', 'N/A')}")
    print(f"Tests: {test_results.get('total_tests', 0)} total, {test_results.get('passed', 0)} passed")
    print("=" * 60)

if __name__ == "__main__":
    main()