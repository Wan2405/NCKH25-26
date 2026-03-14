"""
MODULE AUTO FIXER - Tự động sửa code cho đến khi pass
"""

import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import json

import sys
sys.path.insert(0, os.path.dirname(__file__))
from log_processor import LogProcessor
from error_classifier import ErrorClassifier
from feedback_generator import FeedbackGenerator

class AutoFixer:
    def __init__(self, max_iterations=5, use_docker=False):
        self.max_iterations = max_iterations
        self.use_docker = use_docker
        
        self.log_processor = LogProcessor()
        self.error_classifier = ErrorClassifier(use_llm=True)
        self.feedback_gen = FeedbackGenerator()
        
        self.maven_project = Path("auto_grader/maven_project")
        self.output_dir = Path("auto_grader/output/auto_fix_history")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    def fix_until_pass(self, problem_id, initial_code, problem_description, class_name=None):
        """Vòng lặp chính: Sửa cho đến khi pass"""
        
        if class_name is None:
            class_name = self._extract_class_name(initial_code, problem_id)
        
        current_code = initial_code
        history = []
        
        print("\n" + "=" * 70)
        print("BẮT ĐẦU AUTO-FIX LOOP")
        print("=" * 70)
        for iteration in range(1, self.max_iterations + 1):
            print("\n[ITERATION {}/{}]".format(iteration, self.max_iterations))
            print("-" * 70)
            
            # Lưu code vào Maven
            self._save_to_maven_project(class_name, current_code)
            
            # Chạy test
            test_log = self._run_maven_test()
            
            # Xử lý log
            log_data = self._process_log(problem_id, iteration)
            
            # Phân loại lỗi
            classification = self.error_classifier.classify(log_data)
            
            # Lưu history
            iteration_data = {
                'iteration': iteration,
                'code': current_code,
                'error_type': classification['loai_loi'],
                'error_reason': classification['nguyen_nhan'],
                'test_results': log_data.get('test_results', {}),
                'timestamp': datetime.now().isoformat()
            }
            history.append(iteration_data)
            # Kiểm tra pass chưa?
            if classification['loai_loi'] == 'PASSED':
                print("\nCODE ĐÃ PASS SAU {} LẦN!".format(iteration))
                return {
                    'success': True,
                    'iterations': iteration,
                    'final_code': current_code,
                    'history': history,
                    'problem_id': problem_id
                }
            
            # Nếu chưa pass → Gọi LLM sửa
            print("Test failed: {}".format(classification['loai_loi']))
            print("Nguyên nhân: {}...".format(str(classification['nguyen_nhan'])[:100]))
            
            if iteration < self.max_iterations:
                print("Đang gọi LLM sửa code...")
                
                feedback = self.feedback_gen.generate_fix_suggestion(
                    current_code,
                    classification,
                    problem_description
                )
                
                if 'fixed_code' in feedback and feedback['fixed_code']:
                    current_code = feedback['fixed_code']
                    iteration_data['fixed_code'] = current_code
                    iteration_data['fix_explanation'] = feedback.get('explanation', '')
                    print("LLM đã đề xuất code mới")
                else:
                    print("LLM không sinh được code sửa")
                    break
        # Hết số lần thử
        print("\nKHÔNG THỂ SỬA SAU {} LẦN".format(self.max_iterations))
        return {
            'success': False,
            'iterations': self.max_iterations,
            'final_code': current_code,
            'last_error': classification['loai_loi'],
            'history': history,
            'problem_id': problem_id
        }
    def _extract_class_name(self, code, problem_id):
        """Tự động tìm tên class"""
        import re
        match = re.search(r'public\s+class\s+(\w+)', code)
        if match:
            return match.group(1)
        return "{}_Solution".format(problem_id)
    
    def _save_to_maven_project(self, class_name, code):
        """Lưu code vào Maven"""
        dest = self.maven_project / "src" / "main" / "java" / "com" / "example" / "{}.java".format(class_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(code)
    def _run_maven_test(self):
        """Chạy Maven test"""
        
        if self.use_docker:
            from auto_grader.docker.run_in_docker import get_docker_runner
            runner = get_docker_runner()
            return runner.run_test(str(self.maven_project))
        
        # Local
        mvn_cmd = "mvn.cmd" if os.name == 'nt' else "mvn"
        
        result = subprocess.run(
            [mvn_cmd, "clean", "test"],
            cwd=str(self.maven_project),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        full_log = result.stdout
        if result.stderr:
            full_log += "\n--- ERROR STREAM ---\n" + result.stderr
        full_log += "\n--- EXIT CODE: {} ---".format(result.returncode)
        
        # Lưu log
        log_file = Path("auto_grader/grading_history.txt")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(full_log)
        
        return full_log
    def _process_log(self, problem_id, iteration):
        """Xử lý log"""
        log_data = self.log_processor.process_log(
            log_path="auto_grader/grading_history.txt",
            student_id="AUTO_FIX_IT{}".format(iteration),
            problem_id=problem_id
        )
        return log_data
    
    def save_history(self, fix_result):
        """Lưu lịch sử"""
        problem_id = fix_result['problem_id']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        filename = "{}_autofix_{}.json".format(problem_id, timestamp)
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(fix_result, f, indent=2, ensure_ascii=False)
        
        print("\nĐã lưu lịch sử: {}".format(filepath))
        return str(filepath)
