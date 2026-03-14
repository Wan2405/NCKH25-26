"""
PHÂN LOẠI LỖI - Đơn giản
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from auto_grader.modules.error_classifier import ErrorClassifier

def main():
    print("=" * 60)
    print("🤖 PHÂN LOẠI LỖI")
    print("=" * 60)
    
    # Tìm file log JSON mới nhất
    log_dir = Path("auto_grader/output/logs")
    if not log_dir.exists():
        print("❌ Chưa có log!")
        print("💡 Hãy chạy: python runner.py trước")
        return
    
    log_files = list(log_dir.glob("*.json"))
    if not log_files:
        print("❌ Không tìm thấy file log JSON!")
        return
    
    latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
    print(f"\n📂 Đang phân tích: {latest_log.name}")
    
    # Đọc log
    with open(latest_log, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
    
    # Phân loại
    print("[*] Đang phân tích...")
    classifier = ErrorClassifier(use_llm=True)
    result = classifier.classify(log_data)
    
    # Hiển thị
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ:")
    print("=" * 60)
    print(f"Loại lỗi: {result['loai_loi']}")
    print(f"Nguyên nhân: {result['nguyen_nhan'][:100]}...")
    print("=" * 60)
    
    # Lưu kết quả
    output_file = classifier.save_result(result, log_data)
    print(f"\n✅ Đã lưu: {output_file}")

if __name__ == "__main__":
    main()