"""
code_generator.py

Mục đích:
    Sinh code Java từ đề bài sử dụng LLM.
    Dùng để tạo code mẫu hoặc code khởi đầu cho sinh viên.

Cách hoạt động:
    1. Nhận đề bài và tên class mong muốn
    2. Xây dựng prompt yêu cầu LLM sinh code
    3. Gọi API Ollama (có retry)
    4. Trả về code Java hoàn chỉnh
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime

class CodeGenerator:
    """
    Sinh code Java từ đề bài.
    
    Tham số:
        ollama_url: URL API Ollama
    """
    
    def __init__(self, ollama_url="http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url
        self.output_dir = Path("auto_grader/output/generated_code")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_from_problem(self, problem_id, problem_description, class_name=None, max_retries=3):
        """
        Sinh code Java từ đề bài.
        
        Tham số:
            problem_id: ID bài tập (vd: P001)
            problem_description: Mô tả đề bài
            class_name: Tên class mong muốn (tự động nếu không đặt)
            max_retries: Số lần retry nếu API lỗi
        
        Trả về:
            Dict chứa code, explanation, method_name
        """
        
        if class_name is None:
            class_name = "{}_Solution".format(problem_id)

        # Prompt tiếng Việt không dấu (tránh lỗi encoding với Ollama)
        prompt = """Ban la Java expert. Viet code Java hoan chinh cho bai tap sau:

DE BAI:
{desc}

YEU CAU:
1. Package: com.example
2. Ten class: {cls}
3. Code phai compile duoc

VI DU:
package com.example;
public class {cls} {{
    public static int method(int a) {{
        return a;
    }}
}}

TRA VE JSON (khong co markdown):
{{"code": "...", "explanation": "...", "method_name": "...", "return_type": "int"}}
""".format(desc=problem_description, cls=class_name)

        # Retry với exponential backoff
        for attempt in range(max_retries):
            backoff_time = 2 ** attempt
            try:
                print("Dang sinh code (lan {}/{})...".format(attempt+1, max_retries))
                
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": "llama3.1",
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 1000}
                    },
                    timeout=120
                )
                
                response.raise_for_status()
                result = response.json()
                generated = json.loads(result.get('response', '{}'))
                if 'code' in generated and generated['code'].strip():
                    print("LLM da sinh code thanh cong!")
                    generated['method'] = 'llm'
                    generated['attempt'] = attempt + 1
                    generated['generated_at'] = datetime.now().isoformat()
                    generated['problem_id'] = problem_id
                    return generated
                else:
                    print("LLM tra ve code rong, retry sau {}s...".format(backoff_time))
                    time.sleep(backoff_time)
                    
            except requests.ConnectionError:
                print("Khong ket noi duoc Ollama, retry sau {}s...".format(backoff_time))
                time.sleep(backoff_time)
            except requests.Timeout:
                print("Timeout, retry sau {}s...".format(backoff_time))
                time.sleep(backoff_time)
            except Exception as e:
                print("Loi: {}, retry sau {}s...".format(e, backoff_time))
                time.sleep(backoff_time)

        # Hết retry → Trả về template đơn giản
        print("Khong the sinh code, dung template")
        return {
            'code': 'package com.example;\n\npublic class {} {{}}'.format(class_name),
            'explanation': 'Template (LLM failed)',
            'method': 'fallback',
            'generated_at': datetime.now().isoformat(),
            'problem_id': problem_id
        }

    def save_generated_code(self, problem_id, code_data):
        """Lưu code đã sinh ra file JSON và Java."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        json_file = self.output_dir / "{}_generated_{}.json".format(problem_id, timestamp)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(code_data, f, indent=2, ensure_ascii=False)
        
        java_file = self.output_dir / "{}_generated_{}.java".format(problem_id, timestamp)
        with open(java_file, 'w', encoding='utf-8') as f:
            f.write(code_data['code'])
        
        print("Da luu: {}".format(java_file))
        return str(java_file)
