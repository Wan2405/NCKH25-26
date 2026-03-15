"""
error_classifier.py

Mục đích:
    Phân loại lỗi Java chi tiết hơn LogProcessor.
    Kết hợp Regex (nhanh) và LLM (chính xác) để xác định nguyên nhân lỗi.

Cách hoạt động:
    1. Quick classify: Dùng regex tìm các pattern lỗi phổ biến
    2. Nếu confidence thấp (<0.8) → Gọi LLM phân tích sâu hơn
    3. Trả về loại lỗi, nguyên nhân và gợi ý sửa
"""

import requests
import json
import re
import time
from pathlib import Path

class ErrorClassifier:
    """
    Phân loại lỗi với 2 chiến lược:
        1. Quick Classification (Regex) - nhanh, không cần LLM
        2. LLM Classification (Llama 3.1) - chính xác hơn, có retry
    
    Tham số:
        use_llm: Có dùng LLM không (nếu False, chỉ dùng regex)
        ollama_url: URL API Ollama
    """
    
    # Giới hạn ký tự log gửi LLM (tránh prompt quá dài)
    STDOUT_LIMIT = 2000
    STDERR_LIMIT = 1000
    DETAIL_LIMIT = 500
    
    def __init__(self, use_llm=True, ollama_url="http://localhost:11434/api/generate"):
        self.use_llm = use_llm
        self.ollama_url = ollama_url
        self.output_dir = Path("auto_grader/output/classifications")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Các pattern để nhận diện lỗi nhanh (không cần LLM)
        self.error_patterns = {
            'COMPILE_ERROR': {
                'keywords': ['COMPILATION ERROR', 'cannot find symbol', 'illegal start'],
                'confidence': 0.9  # Độ tin cậy cao vì pattern rõ ràng
            },
            'RUNTIME_ERROR': {
                'keywords': ['Exception in thread', 'NullPointerException', 'ArrayIndexOutOfBoundsException'],
                'confidence': 0.85
            },
            'TEST_FAILED': {
                'keywords': ['Failures: [1-9]', 'expected:<.*> but was:<.*>', 'AssertionError'],
                'confidence': 0.9
            },
            'PASSED': {
                'keywords': ['BUILD SUCCESS', 'Failures: 0'],
                'confidence': 0.95
            }
        }
    
    def quick_classify(self, log_data):
        """
        Phân loại nhanh bằng Regex.
        Không cần gọi LLM, phù hợp cho lỗi phổ biến.
        """
        
        full_text = log_data.get('raw_logs', {}).get('stdout', '') + \
                   log_data.get('raw_logs', {}).get('stderr', '')
        
        error_type = log_data.get('execution', {}).get('error_type', 'UNKNOWN')
        
        for category, info in self.error_patterns.items():
            for keyword in info['keywords']:
                if re.search(keyword, full_text, re.IGNORECASE):
                    return {
                        'method': 'regex',
                        'loai_loi': category,
                        'nguyen_nhan': 'Detected pattern: {}'.format(keyword),
                        'confidence': info['confidence'],
                        'goi_y': self._get_quick_suggestion(category),
                        'chi_tiet': self._safe_str(log_data.get('execution', {}).get('error_detail', ''))[:self.DETAIL_LIMIT]
                    }
        
        return {
            'method': 'regex',
            'loai_loi': error_type if error_type != 'UNKNOWN' else 'UNKNOWN',
            'nguyen_nhan': 'Không khớp pattern chuẩn',
            'confidence': 0.3,
            'goi_y': 'Cần phân tích bằng LLM',
            'chi_tiet': ''
        }
    
    def _safe_str(self, value):
        """Chuyển list/dict/any thành string an toàn."""
        if isinstance(value, list):
            return '\n'.join(str(item) for item in value)
        return str(value)
    
    def llm_classify(self, log_data, max_retries=3):
        """
        Phân loại bằng LLM với exponential backoff.
        
        Gọi API Ollama để LLM phân tích log chi tiết hơn.
        Nếu LLM không phản hồi, fallback về quick_classify.
        """
        
        error_type = log_data.get('execution', {}).get('error_type', 'UNKNOWN')
        error_detail = log_data.get('execution', {}).get('error_detail', '')
        test_results = log_data.get('test_results', {})
        stdout = log_data.get('raw_logs', {}).get('stdout', '')[-self.STDOUT_LIMIT:]
        stderr = log_data.get('raw_logs', {}).get('stderr', '')[-self.STDERR_LIMIT:]
        
        # Prompt tiếng Việt cho Llama 3.1
        prompt_template = """Bạn là AI chuyên phân tích lỗi Java.

**Thông tin:**
- Problem ID: {problem_id}
- Error Type: {error_type}
- Exit Code: {exit_code}

**Test Results:**
- Total: {total_tests}
- Passed: {passed}
- Failed: {failed}

**Chi tiết lỗi:**
{error_detail}

**Maven Output:**
{stdout}

**Error Stream:**
{stderr}

Phân tích và trả về JSON:
{{
  "loai_loi": "COMPILE_ERROR|RUNTIME_ERROR|LOGIC_ERROR|PASSED",
  "nguyen_nhan": "Mô tả ngắn gọn",
  "chi_tiet": "Giải thích cụ thể",
  "goi_y": "Hướng dẫn sửa lỗi"
}}
"""
        
        # Chuyển error_detail thành string (có thể là list)
        error_detail_str = self._safe_str(error_detail)
        
        prompt = prompt_template.format(
            problem_id=log_data.get('metadata', {}).get('problem_id', 'N/A'),
            error_type=error_type,
            exit_code=log_data.get('execution', {}).get('exit_code', 'N/A'),
            total_tests=test_results.get('total_tests', 0),
            passed=test_results.get('passed', 0),
            failed=test_results.get('failed', 0),
            error_detail=error_detail_str,
            stdout=stdout,
            stderr=stderr
        )

        # Retry với exponential backoff: 1s, 2s, 4s
        for attempt in range(max_retries):
            backoff_time = 2 ** attempt
            try:
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": "llama3.1",
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.2}
                    },
                    timeout=90
                )
                
                if response.status_code == 200:
                    llm_result = json.loads(response.json()['response'])
                    llm_result['method'] = 'llm'
                    llm_result['confidence'] = 0.95
                    return llm_result
                else:
                    print("⚠️ Ollama returned {}, retry sau {}s...".format(
                        response.status_code, backoff_time))
                    time.sleep(backoff_time)
                    
            except requests.ConnectionError:
                print("⚠️ Không kết nối được Ollama, retry sau {}s...".format(backoff_time))
                time.sleep(backoff_time)
            except requests.Timeout:
                print("⚠️ Timeout, retry sau {}s...".format(backoff_time))
                time.sleep(backoff_time)
            except Exception as e:
                print("⚠️ LLM Error: {}, retry sau {}s...".format(str(e), backoff_time))
                time.sleep(backoff_time)
        
        # Hết retry → Dùng regex fallback
        print("⚠️ LLM không phản hồi sau {} lần. Dùng Regex fallback.".format(max_retries))
        return self.quick_classify(log_data)
    
    def classify(self, log_data):
        """
        HÀM CHÍNH: Phân loại lỗi.
        
        Chiến lược:
            1. Chạy quick_classify trước (nhanh)
            2. Nếu confidence < 0.8 và use_llm=True → Gọi LLM
        """
        
        # Quick classify trước (không cần LLM)
        quick_result = self.quick_classify(log_data)
        
        # Nếu confidence thấp và có LLM → Dùng LLM để phân tích kỹ hơn
        if quick_result['confidence'] < 0.8 and self.use_llm:
            print("🤖 Đang phân tích bằng LLM...")
            return self.llm_classify(log_data)
        
        return quick_result
    
    def _get_quick_suggestion(self, error_type):
        """Gợi ý sửa lỗi nhanh dựa vào loại lỗi."""
        suggestions = {
            'COMPILE_ERROR': '1. Kiểm tra cú pháp Java\n2. Kiểm tra import\n3. Kiểm tra tên class',
            'RUNTIME_ERROR': '1. Kiểm tra null pointer\n2. Kiểm tra index array',
            'TEST_FAILED': '1. So sánh output với expected\n2. Kiểm tra logic',
            'PASSED': 'Code đã pass!',
            'UNKNOWN': 'Cần xem lại log'
        }
        return suggestions.get(error_type, 'Không có gợi ý')
    
    def save_result(self, classification, log_data):
        """Lưu kết quả phân loại ra file JSON."""
        
        problem_id = log_data.get('metadata', {}).get('problem_id', 'unknown')
        student_id = log_data.get('metadata', {}).get('student_id', 'unknown')
        
        filename = "{}_{}_classification.json".format(problem_id, student_id)
        output_path = self.output_dir / filename
        
        full_result = {
            'metadata': log_data.get('metadata'),
            'classification': classification
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(full_result, f, indent=2, ensure_ascii=False)
        
        print("✅ Đã lưu classification: {}".format(output_path))
        return str(output_path)


# === TEST ===
# Chạy file này trực tiếp để test ErrorClassifier
if __name__ == '__main__':
    import json
    from pathlib import Path
    
    print("🧪 TEST ERROR CLASSIFIER")
    
    log_files = list(Path("auto_grader/output/logs").glob("*.json"))
    
    if not log_files:
        print("❌ Không tìm thấy log JSON. Chạy runner.py trước!")
        exit(1)
    
    latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
    
    with open(latest_log, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
    
    classifier = ErrorClassifier(use_llm=True)
    result = classifier.classify(log_data)
    
    print("\n📊 KẾT QUẢ:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    classifier.save_result(result, log_data)