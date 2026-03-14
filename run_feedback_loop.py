"""
AUTO-FIX LOOP - Tự động sửa lỗi nhiều vòng (với Docker)
Vòng lặp: test (Docker) → phân loại → sửa (LLM) → test lại (Docker) → lặp tới k vòng
"""

import sys
import os
import json
from pathlib import Path

import subprocess as _subprocess

sys.path.insert(0, os.path.dirname(__file__))
from auto_grader.modules.feedback_generator import FeedbackGenerator
from auto_grader.modules.log_processor import LogProcessor
from auto_grader.modules.error_classifier import ErrorClassifier
import runner

PROBLEMS = {
    'P001': {
        'title': 'Tong hai so',
        'description': 'Viet ham tinhTong(int a, int b) tra ve tong a + b',
        'input_file': 'auto_grader/input_code/P001_TongHaiSo.java'
    },
    'P002': {
        'title': 'Tinh giai thua',
        'description': 'Viet ham tinhGiaiThua(int n) tra ve n!',
        'input_file': 'auto_grader/input_code/P002_TinhGiaiThua.java'
    },
    'P003': {
        'title': 'Kiem tra so nguyen to',
        'description': 'Viet ham kiemTraNguyenTo(int n) tra ve true neu n la so nguyen to',
        'input_file': 'auto_grader/input_code/P003_KiemTraNguyenTo.java'
    },
    'P004': {
        'title': 'Tim max trong mang',
        'description': 'Viet ham timMax(int[] arr) tra ve phan tu lon nhat',
        'input_file': 'auto_grader/input_code/P004_TimMax.java'
    },
    'P005': {
        'title': 'Dao nguoc chuoi',
        'description': 'Viet ham daoNguoc(String s) tra ve chuoi dao nguoc',
        'input_file': 'auto_grader/input_code/P005_DaoNguocChuoi.java'
    },
}

def read_latest_classification():
    """
    Đọc kết quả phân loại lỗi từ file JSON mới nhất
    """
    classification_dir = Path("auto_grader/output/classifications")
    classification_dir.mkdir(parents=True, exist_ok=True)
    
    json_files = list(classification_dir.glob("*.json"))
    
    if not json_files:
        return {
            'loai_loi': 'Unknown',
            'nguyen_nhan': 'Chưa phân loại',
            'goi_y': ''
        }
    
    latest = max(json_files, key=lambda x: x.stat().st_mtime)
    
    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get("classification", {})

def auto_fix_loop(problem_id, max_rounds=3):
    """
    Vòng lặp auto-fix với Docker:
    Vòng 1: test (Docker) → phân loại lỗi → sửa (LLM)
    Vòng 2: test code mới (Docker) → phân loại lỗi → sửa (LLM)
    ... lặp tới khi pass hoặc hết max_rounds
    """
    
    print("=" * 70)
    print("[*] AUTO-FIX LOOP - START (với Docker)")
    print("=" * 70)
    
    if problem_id not in PROBLEMS:
        print(f"[!] Không tìm thấy bài: {problem_id}")
        return []
    
    problem = PROBLEMS[problem_id]
    code_file = problem['input_file']
    
    if not os.path.exists(code_file):
        print(f"[!] Không tìm thấy file: {code_file}")
        return []
    
    with open(code_file, 'r', encoding='utf-8') as f:
        original_code = f.read()
    
    current_code = original_code
    feedback_gen = FeedbackGenerator()
    history = []
    
    for round_num in range(1, max_rounds + 1):
        print(f"\n🟡 VÒNG {round_num}/{max_rounds}")
        print("-" * 70)
        
        # BƯỚC 1: Test code hiện tại (🐳 QUA DOCKER)
        print(f"[*] Đang chạy test (🐳 Docker)...")
        sys.argv = ["runner.py", problem_id, code_file, "SV001"]
        runner.main()
        
        # BƯỚC 2: Phân loại lỗi
        print(f"[*] Đang phân loại lỗi...")
        _subprocess.run(
            [sys.executable, "phan_loai_loi.py"],
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL
        )
        error_result = read_latest_classification()
        
        # BƯỚC 3: Kiểm tra pass chưa?
        if error_result.get('loai_loi') == 'PASSED':
            print(f"\n✅ PASSED SAU {round_num} VÒNG!")
            history.append({
                'round': round_num,
                'status': 'PASSED',
                'error_type': 'PASSED',
                'run_in_docker': True
            })
            break
        
        # BƯỚC 4: Sinh sửa lỗi từ LLM
        print(f"[*] Lỗi: {error_result.get('loai_loi', 'Unknown')}")
        print(f"[*] Gọi LLM sửa code...")
        
        suggestion = feedback_gen.generate_fix_suggestion(
            current_code,
            error_result,
            problem['description']
        )
        
        # BƯỚC 5: Cập nhật code
        fixed_code = suggestion.get('fixed_code', None)
        
        if not fixed_code or fixed_code.strip() == '':
            print(f"[!] LLM không sinh được code sửa, dừng loop")
            history.append({
                'round': round_num,
                'status': 'FAILED_TO_FIX',
                'error_type': error_result.get('loai_loi', 'Unknown'),
                'run_in_docker': True
            })
            break
        
        # Ghi code mới vào file
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        
        current_code = fixed_code
        print(f"[+] Đã cập nhật code (bản sửa lần {round_num})")
        
        history.append({
            'round': round_num,
            'status': 'FIXED',
            'error_type': error_result.get('loai_loi', 'Unknown'),
            'explanation': suggestion.get('explanation', '')[:100],
            'run_in_docker': True
        })
    
    # Kết thúc loop
    print("\n" + "=" * 70)
    print("[*] AUTO-FIX LOOP - KẾT THÚC")
    print("=" * 70)
    
    # Lưu lịch sử
    history_dir = Path("auto_grader/output/auto_fix_history")
    history_dir.mkdir(parents=True, exist_ok=True)
    
    history_file = history_dir / f"{problem_id}_loop_history.json"
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    
    print(f"\n[+] Lịch sử loop đã lưu: {history_file}")
    print(f"\n📊 Tổng cộng: {len(history)} vòng")
    for h in history:
        docker_tag = "🐳" if h.get('run_in_docker') else ""
        print(f"  Vòng {h['round']}: {h['status']} ({h.get('error_type', 'N/A')}) {docker_tag}")
    
    # Khôi phục code gốc nếu không pass
    if history and history[-1]['status'] != 'PASSED':
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(original_code)
        print(f"\n[*] Code đã khôi phục về version gốc")
    
    return history

def main():
    if len(sys.argv) < 2:
        print("[!] Cách dùng: python run_feedback_loop.py P001 [--max-rounds 3]")
        print("\nDanh sách bài tập:")
        for pid, info in PROBLEMS.items():
            print(f"  - {pid}: {info['title']}")
        sys.exit(1)
    
    problem_id = sys.argv[1]
    max_rounds = 3
    
    if '--max-rounds' in sys.argv:
        idx = sys.argv.index('--max-rounds')
        if idx + 1 < len(sys.argv):
            max_rounds = int(sys.argv[idx + 1])
    
    auto_fix_loop(problem_id, max_rounds)

if __name__ == "__main__":
    main()