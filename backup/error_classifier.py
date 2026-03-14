"""
MODULE ERROR CLASSIFIER - IMPROVED
"""

import requests
import json
import re
import time
from pathlib import Path

class ErrorClassifier:
    def __init__(self, use_llm=True, ollama_url="http://localhost:11434/api/generate"):
        self.use_llm = use_llm
        self.ollama_url = ollama_url
        self.output_dir = Path("auto_grader/output/classifications")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache để tránh gọi LLM trùng lặp
        self.cache_file = self.output_dir / "_cache.json"
        self.cache = self._load_cache()
        
        # Improved patterns
        self.error_patterns = {
            'COMPILE_ERROR': {
                'keywords': [
                    r'COMPILATION ERROR',
                    r'cannot find symbol',
                    r'illegal start',
                    r'package .* does not exist',
                    r'incompatible types',
                    r'\berror:\s'
                ],
                'confidence': 0.95
            },
            'RUNTIME_ERROR': {
                'keywords': [
                    r'Exception in thread',
                    r'NullPointerException',
                    r'ArrayIndexOutOfBoundsException',
                    r'ArithmeticException'
                ],
                'confidence': 0.9
            },
            'TEST_FAILED': {
                'keywords': [
                    r'Failures:\s*[1-9]',
                    r'expected:<.*> but was:<.*>',
                    r'AssertionError',
                    r'FAILURE!',
                    r'FAILED'
                ],
                'confidence': 0.9
            },
            'PASSED': {
                'keywords': [
                    r'BUILD SUCCESS',
                    r'Failures:\s*0.*Errors:\s*0'
                ],
                'confidence': 0.98
            }
        }
    
    def _load_cache(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def _generate_cache_key(self, log_data):
        """Generate unique key for caching"""
        error_type = log_data.get('execution', {}).get('error_type', '')
        error_detail = str(log_data.get('execution', {}).get('error_detail', ''))
        return f"{error_type}_{hash(error_detail[:500])}"
    
    def llm_classify(self, log_data, max_retries=3):
        """
        IMPROVED: Shorter prompt, retry logic, caching
        """
        
        # Check cache first
        cache_key = self._generate_cache_key(log_data)
        if cache_key in self.cache:
            print("✅ Sử dụng kết quả từ cache")
            cached = self.cache[cache_key]
            cached['method'] = 'llm_cached'
            return cached
        
        error_type = log_data.get('execution', {}).get('error_type', 'UNKNOWN')
        error_detail = log_data.get('execution', {}).get('error_detail', '')
        test_results = log_data.get('test_results', {})
        
        # ✅ SHORTER PROMPT - Only send relevant parts
        if isinstance(error_detail, list):
            error_snippet = '\n'.join(error_detail[:3])  # First 3 errors only
        else:
            error_snippet = str(error_detail)[:800]  # Max 800 chars
        
        # Get relevant log section only
        stdout = log_data.get('raw_logs', {}).get('stdout', '')
        
        # Extract only error section from stdout
        if 'COMPILATION ERROR' in stdout:
            # Get from "COMPILATION ERROR" onwards
            relevant_section = stdout[stdout.find('COMPILATION ERROR'):stdout.find('COMPILATION ERROR')+1000]
        elif 'BUILD FAILURE' in stdout:
            relevant_section = stdout[stdout.find('BUILD FAILURE')-500:stdout.find('BUILD FAILURE')+500]
        else:
            relevant_section = stdout[-800:]  # Last 800 chars
        
        prompt = f"""Bạn là AI phân tích lỗi Java. Phân tích ngắn gọn.

**Thông tin:**
- Error Type: {error_type}
- Exit Code: {log_data.get('execution', {}).get('exit_code', 'N/A')}
- Tests: {test_results.get('failed', 0)} failed / {test_results.get('total_tests', 0)} total

**Lỗi chính:**
{error_snippet}

**Log đoạn liên quan:**
{relevant_section}

Trả về JSON ngắn gọn:
{{
  "loai_loi": "COMPILE_ERROR|RUNTIME_ERROR|LOGIC_ERROR|TEST_FAILED|PASSED",
  "nguyen_nhan": "1 câu ngắn gọn",
  "chi_tiet": "2-3 dòng giải thích",
  "goi_y": "Gợi ý sửa cụ thể"
}}
"""

        # Retry logic
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.ollama_url,
                    json={
                        "model": "llama3.1",
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Lower for consistency
                            "num_predict": 300   # Limit output length
                        }
                    },
                    timeout=45
                )
                
                if response.status_code == 200:
                    llm_result = json.loads(response.json()['response'])
                    llm_result['method'] = 'llm'
                    llm_result['confidence'] = 0.92
                    
                    # Save to cache
                    self.cache[cache_key] = llm_result
                    self._save_cache()
                    
                    return llm_result
                else:
                    print(f"⚠️ Ollama returned {response.status_code}, retry {attempt+1}/{max_retries}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
            except requests.Timeout:
                print(f"⚠️ Timeout, retry {attempt+1}/{max_retries}")
                time.sleep(2)
            except Exception as e:
                print(f"⚠️ LLM Error: {e}, retry {attempt+1}/{max_retries}")
                time.sleep(1)
        
        # All retries failed → fallback
        print("❌ LLM failed after retries. Using regex fallback.")
        return self.quick_classify(log_data)
    
    def classify(self, log_data):
        """
        IMPROVED: Smarter decision logic
        """
        
        # Quick classify first
        quick_result = self.quick_classify(log_data)
        
        # Decision: When to use LLM?
        should_use_llm = (
            self.use_llm and 
            (
                quick_result['confidence'] < 0.85 or  # Low confidence
                quick_result['loai_loi'] == 'UNKNOWN' or  # Unknown type
                quick_result['loai_loi'] == 'TEST_FAILED'  # Need detailed analysis
            )
        )
        
        if should_use_llm:
            print("🤖 Sử dụng LLM để phân tích chi tiết...")
            return self.llm_classify(log_data)
        
        return quick_result