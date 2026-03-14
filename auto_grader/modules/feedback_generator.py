"""
MODULE FEEDBACK GENERATOR - IMPROVED VERSION
Tạo gợi ý sửa lỗi từ LLM với retry + exponential backoff
"""

import requests
import json
import os
import time
from pathlib import Path
from datetime import datetime

class FeedbackGenerator:
    
    def __init__(self, ollama_url="http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url
        self.output_dir = Path("auto_grader/output/feedback")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_fix_suggestion(self, student_code, error_analysis, problem_description="", max_retries=3):
        loai_loi = error_analysis.get('loai_loi', 'Unknown')
        nguyen_nhan = error_analysis.get('nguyen_nhan', 'Unknown')
        chi_tiet = error_analysis.get('chi_tiet', '')
        
        # Trích xuất phần code quan trọng nếu quá dài
        code_snippet = student_code
        if len(student_code) > 3000:
            main_idx = student_code.find('public static void main')
            if main_idx > 0:
                code_snippet = student_code[max(0, main_idx-500):main_idx+2000]
            else:
                code_snippet = student_code[:3000]
        
        prompt = "Bạn là Java Tutor. Sinh viên gặp lỗi, hãy hướng dẫn sửa.\n\n"
        prompt += "ĐỀ BÀI:\n"
        prompt += problem_description if problem_description else "Bài tập Java cơ bản"
        prompt += "\n\nCODE CỦA SINH VIÊN:\n"
        prompt += code_snippet
        prompt += "\n\nLỖI PHÁT HIỆN:\n"
        prompt += f"- Loại lỗi: {loai_loi}\n"
        prompt += f"- Nguyên nhân: {nguyen_nhan}\n"
        # Chuyển chi_tiet thành string an toàn (có thể là list)
        chi_tiet_str = '\n'.join(chi_tiet) if isinstance(chi_tiet, list) else str(chi_tiet)
        prompt += f"- Chi tiết: {chi_tiet_str[:500]}\n\n"
        prompt += "YÊU CẦU:\n"
        prompt += "1. Giải thích lỗi ngắn gọn (2-3 câu)\n"
        prompt += "2. Đưa ra code chính xác để sửa\n"
        prompt += "3. Giải thích vì sao\n\n"
        prompt += 'Trả về JSON: {"explanation": "...", "fixed_code": "...", "reasoning": "..."}'
        
        # Retry với exponential backoff
        for attempt in range(max_retries):
            backoff_time = 2 ** attempt  # 1s, 2s, 4s
            try:
                print(f"🤖 Đang gọi LLM (lần {attempt+1}/{max_retries})...")
                
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": "llama3.1",
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 1000, "top_p": 0.9}
                    },
                    timeout=90
                )
                
                response.raise_for_status()
                result = response.json()
                
                try:
                    feedback = json.loads(result.get('response', '{}'))
                    required_fields = ['explanation', 'fixed_code', 'reasoning']
                    
                    if all(field in feedback for field in required_fields):
                        feedback['generated_at'] = datetime.now().isoformat()
                        feedback['model'] = 'llama3.1'
                        feedback['error_type'] = loai_loi
                        feedback['attempt'] = attempt + 1
                        print("✅ LLM response hợp lệ!")
                        return feedback
                    else:
                        missing = [f for f in required_fields if f not in feedback]
                        print(f"⚠️ Thiếu field: {missing}, retry sau {backoff_time}s...")
                        time.sleep(backoff_time)
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️ Lỗi parse JSON: {e}, retry sau {backoff_time}s...")
                    time.sleep(backoff_time)
                    
            except requests.Timeout:
                print(f"⚠️ Timeout, retry sau {backoff_time}s...")
                time.sleep(backoff_time)
            except requests.ConnectionError:
                print(f"⚠️ Không kết nối được Ollama, retry sau {backoff_time}s...")
                time.sleep(backoff_time)
            except Exception as e:
                print(f"⚠️ Lỗi: {e}, retry sau {backoff_time}s...")
                time.sleep(backoff_time)
        
        print("❌ Không thể tạo feedback từ LLM")
        return {
            "error": f"Không thể kết nối LLM sau {max_retries} lần thử",
            "explanation": f"Lỗi: {loai_loi}. {nguyen_nhan}",
            "fixed_code": f"// Không thể tạo code tự động\n// Lỗi: {nguyen_nhan}",
            "reasoning": "LLM không phản hồi. Kiểm tra: ollama serve, ollama pull llama3.1",
            "generated_at": datetime.now().isoformat(),
            "model": "fallback",
            "error_type": loai_loi
        }

    def save_feedback(self, output_file, feedback_data):
        if 'saved_at' not in feedback_data:
            feedback_data['saved_at'] = datetime.now().isoformat()
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Đã lưu feedback: {output_file}")
        
        md_file = str(output_path).replace('.json', '.md')
        self._save_as_markdown(md_file, feedback_data)
    
    def _save_as_markdown(self, md_file, feedback_data):
        try:
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write("# FEEDBACK - GỢI Ý SỬA LỖI\n\n")
                f.write(f"**Thời gian:** {feedback_data.get('generated_at', 'N/A')}\n\n")
                f.write(f"**Model:** {feedback_data.get('model', 'N/A')}\n\n")
                f.write(f"**Loại lỗi:** {feedback_data.get('error_type', 'N/A')}\n\n")
                f.write("## 📝 Giải thích lỗi\n\n")
                f.write(feedback_data.get('explanation', 'N/A'))
                f.write("\n\n## 💡 Code đã sửa\n\n```java\n")
                f.write(feedback_data.get('fixed_code', 'N/A'))
                f.write("\n```\n\n## 🤔 Giải thích cách sửa\n\n")
                f.write(feedback_data.get('reasoning', 'N/A'))
                f.write("\n")
            print(f"✅ Đã lưu markdown: {md_file}")
        except Exception as e:
            print(f"⚠️ Không thể tạo markdown: {e}")


if __name__ == '__main__':
    print("=" * 70)
    print("🧪 TEST FEEDBACK GENERATOR")
    print("=" * 70)
    
    sample_code = """
public class TinhTong {
    public static int tinhTong(int a, int b) {
        return a - b;
    }
}
"""
    
    sample_error = {
        'loai_loi': 'TEST_FAILED',
        'nguyen_nhan': 'Kết quả không đúng',
        'chi_tiet': 'Expected: 5, Actual: -1',
        'goi_y': 'Kiểm tra phép tính'
    }
    
    sample_problem = "Viết hàm tinhTong(int a, int b) trả về tổng a + b"
    
    generator = FeedbackGenerator()
    
    print("\n[*] Test generate_fix_suggestion()...")
    feedback = generator.generate_fix_suggestion(sample_code, sample_error, sample_problem)
    
    print("\n[*] Kết quả:")
    print(json.dumps(feedback, indent=2, ensure_ascii=False))
    
    print("\n[*] Test save_feedback()...")
    test_output = "auto_grader/output/feedback/TEST_feedback.json"
    generator.save_feedback(test_output, feedback)
    
    print("\n" + "=" * 70)
    print("✅ TEST HOÀN TẤT")
    print("=" * 70)