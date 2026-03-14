"""
MODULE LOG PROCESSOR - Task 8-9 (IMPROVED)
"""

import re
import json
from datetime import datetime
from pathlib import Path

class LogProcessor:
    def __init__(self, output_dir="auto_grader/output/logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Enhanced patterns
        self.patterns = {
            'compile_error': [
                r'COMPILATION ERROR',
                r'\[ERROR\].*\.java:\[\d+,\d+\]',
                r'cannot find symbol',
                r'class, interface, or enum expected',
                r'illegal start of expression',
                r'package .* does not exist',
                r'incompatible types'
            ],
            'runtime_error': [
                r'Exception in thread',
                r'at\s+[\w\.$]+\([^\)]+\.java:\d+\)',
                r'NullPointerException',
                r'ArrayIndexOutOfBoundsException',
                r'ArithmeticException',
                r'ClassNotFoundException',
                r'NoSuchMethodError'
            ],
            # Support both JUnit 4 and 5
            'test_failed_junit4': r'Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)',
            'test_failed_junit5': r'\[INFO\]\s*Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)',
            'build_success': r'BUILD SUCCESS',
            'build_failure': r'BUILD FAILURE',
            'exit_code': r'exit code:\s*(-?\d+)'
        }
    
    def _extract_compile_error_detail(self, log_text):
        """Improved: Lấy toàn bộ compile errors với context"""
        errors = []
        lines = log_text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Detect error line
            if '[ERROR]' in line and '.java:' in line:
                error_block = [line]
                
                # Collect next 5 lines for context
                for j in range(1, 6):
                    if i + j < len(lines):
                        next_line = lines[i + j]
                        error_block.append(next_line)
                        
                        # Stop if hit next error or empty lines
                        if next_line.strip() == '' or '[ERROR]' in next_line:
                            break
                
                errors.append('\n'.join(error_block))
                i += len(error_block)
            else:
                i += 1
        
        if not errors:
            # Fallback: search for "error:" keyword
            for line in lines:
                if 'error:' in line.lower():
                    errors.append(line)
        
        return errors if errors else ['Compile error không có chi tiết']
    
    def _extract_test_details(self, log_text):
        """Enhanced: Support JUnit 4 & 5"""
        test_info = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0,
            'failed_test_names': []
        }
        
        # Try JUnit 5 first
        match = re.search(self.patterns['test_failed_junit5'], log_text)
        if not match:
            # Fallback to JUnit 4
            match = re.search(self.patterns['test_failed_junit4'], log_text)
        
        if match:
            test_info['total_tests'] = int(match.group(1))
            test_info['failed'] = int(match.group(2))
            test_info['errors'] = int(match.group(3))
            test_info['skipped'] = int(match.group(4))
            test_info['passed'] = (test_info['total_tests'] - 
                                   test_info['failed'] - 
                                   test_info['errors'] - 
                                   test_info['skipped'])
        
        # Extract failed test names
        failed_pattern = r'(?:FAILURE!|FAILED)\s+(\w+)\(([^\)]+)\)'
        for match in re.finditer(failed_pattern, log_text):
            test_info['failed_test_names'].append({
                'method': match.group(1),
                'class': match.group(2)
            })
        
        return test_info
    
    def process_log(self, log_path="auto_grader/grading_history.txt", 
                    student_id="SV001", problem_id="P001"):
        """
        IMPROVED: Không truncate stdout, phân tích kỹ hơn
        """
        log_content, error = self.read_log_file(log_path)
        if error:
            return {'error': error}
        
        # Tách stdout/stderr
        if '--- ERROR STREAM ---' in log_content:
            parts = log_content.split('--- ERROR STREAM ---')
            stdout = parts[0]
            stderr = parts[1].split('--- EXIT CODE:')[0] if len(parts) > 1 else ''
        else:
            stdout = log_content
            stderr = ''
        
        # Phân tích
        error_type, error_detail = self.extract_error_type(log_content)
        test_info = self._extract_test_details(log_content)
        
        # Exit code
        exit_match = re.search(self.patterns['exit_code'], log_content)
        exit_code = int(exit_match.group(1)) if exit_match else None
        
        # Build status
        build_status = 'SUCCESS' if re.search(self.patterns['build_success'], log_content) else 'FAILURE'
        
        result = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'student_id': student_id,
                'problem_id': problem_id,
                'log_file': str(log_path)
            },
            'execution': {
                'exit_code': exit_code,
                'build_status': build_status,
                'error_type': error_type,
                'error_detail': error_detail
            },
            'test_results': test_info,
            'raw_logs': {
                'stdout': stdout,  # ✅ LƯU TOÀN BỘ
                'stderr': stderr,
                'stdout_length': len(stdout),
                'stderr_length': len(stderr)
            }
        }
        
        return result