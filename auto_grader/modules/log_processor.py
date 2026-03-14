"""
MODULE LOG PROCESSOR - Task 8-9
Xử lý log thô từ grading_history.txt thành JSON chuẩn hóa
"""

import re
import json
from datetime import datetime
from pathlib import Path

class LogProcessor:
    """
    Xử lý log từ Maven/JUnit
    """
    
    def __init__(self, output_dir="auto_grader/output/logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Regex patterns
        self.patterns = {
            'compile_error': [
                r'COMPILATION ERROR',
                r'\[ERROR\].*\.java:\[\d+,\d+\]',
                r'cannot find symbol',
                r'class, interface, or enum expected',
                r'illegal start of expression'
            ],
            'runtime_error': [
                r'Exception in thread',
                r'at\s+[\w\.]+\([^\)]+\.java:\d+\)',
                r'NullPointerException',
                r'ArrayIndexOutOfBoundsException',
                r'ArithmeticException'
            ],
            'test_failed': r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)',
            'build_success': r'BUILD SUCCESS',
            'exit_code': r'(?i)exit\s*code:?\s*(\d+)'
        }
    
    def read_log_file(self, log_path="auto_grader/grading_history.txt"):
        """Đọc file log - SỬA LỖI: Thêm method này"""
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                return None, "File log rỗng"
            
            return content, None
            
        except FileNotFoundError:
            return None, "Không tìm thấy file: {}".format(log_path)
        except Exception as e:
            return None, "Lỗi đọc file: {}".format(str(e))
    
    def extract_error_type(self, log_text):
        """Xác định loại lỗi"""
        
        # Kiểm tra BUILD SUCCESS
        if re.search(self.patterns['build_success'], log_text):
            test_match = re.search(self.patterns['test_failed'], log_text)
            if test_match:
                failures = int(test_match.group(2))
                errors = int(test_match.group(3))
                if failures + errors == 0:
                    return 'PASSED', 'All tests passed'
                else:
                    return 'TEST_FAILED', '{} failures, {} errors'.format(failures, errors)
            return 'PASSED', 'Build successful'
        
        # Kiểm tra compile error
        for pattern in self.patterns['compile_error']:
            if re.search(pattern, log_text, re.IGNORECASE):
                return 'COMPILE_ERROR', self._extract_compile_error_detail(log_text)
        
        # Kiểm tra runtime error
        for pattern in self.patterns['runtime_error']:
            if re.search(pattern, log_text):
                return 'RUNTIME_ERROR', self._extract_runtime_error_detail(log_text)
        
        # Kiểm tra test failed
        test_match = re.search(self.patterns['test_failed'], log_text)
        if test_match:
            failures = int(test_match.group(2))
            errors = int(test_match.group(3))
            if failures + errors > 0:
                return 'TEST_FAILED', '{} test failures, {} errors'.format(failures, errors)
        
        return 'UNKNOWN', 'Không xác định được loại lỗi'
    
    def _extract_compile_error_detail(self, log_text):
        """Trích xuất chi tiết lỗi compile"""
        errors = []
        lines = log_text.split('\n')
        
        for i, line in enumerate(lines):
            if '[ERROR]' in line and '.java:' in line:
                context = '\n'.join(lines[i:i+3])
                errors.append(context.strip())
        
        return errors[:3] if errors else ['Lỗi compile không xác định']
    
    def _extract_runtime_error_detail(self, log_text):
        """Trích xuất stack trace"""
        lines = log_text.split('\n')
        
        for i, line in enumerate(lines):
            if 'Exception' in line:
                stack_trace = '\n'.join(lines[i:min(i+10, len(lines))])
                return stack_trace
        
        return 'Runtime error không có stack trace'
    
    def _extract_test_details(self, log_text):
        """Trích xuất thông tin test cases"""
        test_info = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0
        }
        
        match = re.search(self.patterns['test_failed'], log_text)
        if match:
            test_info['total_tests'] = int(match.group(1))
            test_info['failed'] = int(match.group(2))
            test_info['errors'] = int(match.group(3))
            test_info['skipped'] = int(match.group(4))
            test_info['passed'] = test_info['total_tests'] - test_info['failed'] - test_info['errors'] - test_info['skipped']
        
        return test_info
    
    def process_log(self, log_path="auto_grader/grading_history.txt", student_id="SV001", problem_id="P001"):
        """
        HÀM CHÍNH: Đọc log → Phân tích → Tạo JSON
        """
        
        # Đọc file - SỬA LỖI: Gọi read_log_file
        log_content, error = self.read_log_file(log_path)
        if error:
            return {'error': error}
        
        # Tách stdout và stderr
        if '--- ERROR STREAM ---' in log_content:
            parts = log_content.split('--- ERROR STREAM ---')
            stdout = parts[0]
            stderr = parts[1] if len(parts) > 1 else ''
        else:
            stdout = log_content
            stderr = ''
        
        # Phân tích
        error_type, error_detail = self.extract_error_type(log_content)
        test_info = self._extract_test_details(log_content)
        
        # Exit code
        exit_match = re.search(self.patterns['exit_code'], log_content)
        exit_code = int(exit_match.group(1)) if exit_match else None
        
        # Tạo structured data
        result = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'student_id': student_id,
                'problem_id': problem_id,
                'log_file': str(log_path)
            },
            'execution': {
                'exit_code': exit_code,
                'error_type': error_type,
                'error_detail': error_detail
            },
            'test_results': test_info,
            'raw_logs': {
                'stdout': stdout[-2000:],  # Lưu 2000 ký tự cuối
                'stderr': stderr[-1000:] if stderr else ''
            }
        }
        
        return result
    
    def save_json(self, data, filename=None):
        """Lưu JSON"""
        
        if filename is None:
            problem_id = data.get('metadata', {}).get('problem_id', 'unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = "{}_{}.json".format(problem_id, timestamp)
        
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print("✅ Đã lưu log JSON: {}".format(output_path))
        return str(output_path)


# === TEST MODULE ===
if __name__ == '__main__':
    print("🧪 TEST LOG PROCESSOR")
    print("=" * 50)
    
    processor = LogProcessor()
    
    result = processor.process_log(
        log_path="auto_grader/grading_history.txt",
        student_id="SV001",
        problem_id="P001"
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    processor.save_json(result)