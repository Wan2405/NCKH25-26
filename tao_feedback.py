"""
TAO FEEDBACK - Đơn giản
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from auto_grader.modules.feedback_generator import FeedbackGenerator

PROBLEMS = {
    'P001': {
        'title': 'Tong hai so',
        'description': 'Viet ham tinhTong(int a, int b) tra ve tong a + b',
        'code_file': 'auto_grader/input_code/P001_TongHaiSo.java'
    },
    'P002': {
        'title': 'Tinh giai thua',
        'description': 'Viet ham tinhGiaiThua(int n) tra ve n!',
        'code_file': 'auto_grader/input_code/P002_TinhGiaiThua.java'
    }
}

def main():
    print("=" * 60)
    print("🤖 TAO FEEDBACK")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\nCách dùng: python tao_feedback.py P001")
        sys.exit(1)
    
    problem_id = sys.argv[1]
    if problem_id not in PROBLEMS:
        print(f"❌ Không tìm thấy bài: {problem_id}")
        sys.exit(1)
    
    problem = PROBLEMS[problem_id]
    print(f"\n[*] Bài tập: {problem['title']}")
    
    # Đọc code
    code_file = problem['code_file']
    if not os.path.exists(code_file):
        print(f"❌ File không tồn tại: {code_file}")
        sys.exit(1)
    
    with open(code_file, 'r', encoding='utf-8') as f:
        code_content = f.read()
    
    print(f"[+] Đọc code: {len(code_content.splitlines())} dòng")
    
    # Đọc classification từ file JSON mới nhất
    class_dir = Path("auto_grader/output/classifications")
    if not class_dir.exists():
        print("❌ Chưa có kết quả phân loại!")
        return
    
    json_files = list(class_dir.glob("*.json"))
    if not json_files:
        print("❌ Không tìm thấy file phân loại!")
        return
    
    latest = max(json_files, key=lambda x: x.stat().st_mtime)
    with open(latest, 'r', encoding='utf-8') as f:
        class_data = json.load(f)
    
    error_info = class_data.get('classification', {})
    print(f"[+] Loại lỗi: {error_info.get('loai_loi', 'N/A')}")
    
    # Tạo feedback
    print("[*] Đang tạo feedback...")
    feedback_gen = FeedbackGenerator()
    
    suggestion = feedback_gen.generate_fix_suggestion(
        code_content,
        error_info,
        problem['description']
    )
    
    # Lưu
    output_file = os.path.join(
        feedback_gen.output_dir,
        f"feedback_{problem_id}_SV001.json"
    )
    feedback_gen.save_feedback(output_file, suggestion)
    
    print("\n" + "=" * 60)
    print(f"[+] Feedback: {suggestion.get('explanation', 'N/A')[:100]}...")
    print(f"[+] Lưu tại: {output_file}")
    print("=" * 60)

if __name__ == "__main__":
    main()