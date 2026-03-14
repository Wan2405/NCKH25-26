"""
MODULE METRICS - Tính toán metrics (không dùng pandas)
"""

import json
import csv
from pathlib import Path

def calculate_metrics(history_files):
    """Tính toán metrics từ lịch sử auto-fix loop"""
    
    results = []
    
    for history_file in history_files:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        problem_id = history_file.stem.split('_')[0]
        
        # Kiểm tra pass chưa
        passed = False
        rounds_to_pass = None
        
        for h in history:
            if h['status'] == 'PASSED':
                passed = True
                rounds_to_pass = h['round']
                break
        
        results.append({
            'problem_id': problem_id,
            'passed': 'YES' if passed else 'NO',
            'rounds_to_pass': rounds_to_pass if rounds_to_pass else 'N/A',
            'total_rounds': len(history)
        })
    
    return results

def export_csv(results, output_file="auto_grader/output/metrics.csv"):
    """Xuất CSV (không dùng pandas)"""
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['problem_id', 'passed', 'rounds_to_pass', 'total_rounds'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"✅ Đã xuất: {output_file}")

def print_metrics(results):
    """In metrics lên màn hình"""
    print("\n" + "=" * 70)
    print("📊 KẾT QUẢ METRICS")
    print("=" * 70)
    
    total = len(results)
    passed_count = len([r for r in results if r['passed'] == 'YES'])
    
    print(f"Tổng bài: {total}")
    print(f"Pass: {passed_count}")
    if total > 0:
        print(f"Pass-all-tests@3: {(passed_count/total*100):.1f}%")
    else:
        print("Pass-all-tests@3: N/A (không có kết quả)")
    
    print("=" * 70)

if __name__ == "__main__":
    history_dir = Path("auto_grader/output/auto_fix_history")
    history_files = list(history_dir.glob("*_loop_history.json"))
    
    if not history_files:
        print("❌ Chưa có lịch sử auto-fix loop")
        print("💡 Hay chạy: python run_feedback_loop.py P001")
    else:
        results = calculate_metrics(history_files)
        export_csv(results)
        print_metrics(results)