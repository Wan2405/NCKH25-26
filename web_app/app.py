"""
FLASK WEB APP - Auto Grader Web Interface
- Upload code
- Chọn bài tập
- Chạy test (Docker) + Auto-fix loop
- Xem kết quả
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import subprocess
import sys
from pathlib import Path

# Thêm project root vào sys.path để import modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

app = Flask(__name__, template_folder='templates')
CORS(app)

# Tải PROBLEMS từ file JSON hoặc fallback dict
def load_problems():
    """Tải danh sách bài tập từ data/problems.json"""
    json_path = os.path.join(os.path.dirname(__file__), 'data', 'problems.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            problems_list = json.load(f)
        # Convert list to dict keyed by id
        return {p['id']: p for p in problems_list}
    except Exception:
        return {
            'P001': {
                'title': 'Tong hai so',
                'description': 'Viet ham tinhTong(int a, int b) tra ve tong a + b'
            },
            'P002': {
                'title': 'Tinh giai thua',
                'description': 'Viet ham tinhGiaiThua(int n) tra ve n!'
            }
        }

PROBLEMS = load_problems()

@app.route('/')
def index():
    return render_template('index.html', problems=PROBLEMS)

@app.route('/api/problems', methods=['GET'])
def get_problems():
    return jsonify(PROBLEMS)

@app.route('/api/grade', methods=['POST'])
def grade():
    """
    POST /api/grade
    Body: {
        "problem_id": "P001",
        "code": "public class P001_Solution {...}",
        "student_id": "SV001",
        "use_docker": true,
        "use_feedback_loop": true,
        "max_rounds": 3
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400
        problem_id = data.get('problem_id')
        code = data.get('code')
        student_id = data.get('student_id', 'SV001')
        use_feedback_loop = data.get('use_feedback_loop', False)
        max_rounds = data.get('max_rounds', 3)
        
        # Kiểm tra input
        if not problem_id or not code:
            return jsonify({'error': 'Missing problem_id or code'}), 400
        
        if problem_id not in PROBLEMS:
            return jsonify({'error': 'Unknown problem: {}'.format(problem_id)}), 400
        
        # Tạo file code tạm thời
        temp_code_dir = os.path.join(PROJECT_ROOT, "auto_grader", "input_code")
        os.makedirs(temp_code_dir, exist_ok=True)
        
        temp_code_file = os.path.join(temp_code_dir, "{}_Solution.java".format(problem_id))
        with open(temp_code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Chạy runner qua subprocess (an toàn hơn sys.argv hack)
        runner_result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, 'runner.py'),
             problem_id, temp_code_file, student_id],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=180
        )
        
        # Chạy phân loại
        subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, 'phan_loai_loi.py')],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120
        )
        
        # Chạy feedback
        subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, 'tao_feedback.py'), problem_id],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=120
        )
        
        result = {
            'problem_id': problem_id,
            'student_id': student_id,
            'runner_output': runner_result.stdout[-500:] if runner_result.stdout else '',
            'feedback_loop_result': None
        }
        
        # Chạy feedback loop (nếu request)
        if use_feedback_loop:
            loop_result = subprocess.run(
                [sys.executable, os.path.join(PROJECT_ROOT, 'run_feedback_loop.py'),
                 problem_id, '--max-rounds', str(max_rounds)],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=600
            )
            result['feedback_loop_result'] = loop_result.stdout[-1000:] if loop_result.stdout else ''
        
        # Đọc kết quả từ output files
        results = {}
        
        class_dir = Path(os.path.join(PROJECT_ROOT, "auto_grader/output/classifications"))
        if class_dir.exists():
            json_files = list(class_dir.glob("*.json"))
            if json_files:
                latest = max(json_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['classification'] = json.load(f)
        
        feedback_dir = Path(os.path.join(PROJECT_ROOT, "auto_grader/output/feedback"))
        if feedback_dir.exists():
            feedback_files = list(feedback_dir.glob("*{}*.json".format(problem_id)))
            if feedback_files:
                latest = max(feedback_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['feedback'] = json.load(f)
        
        return jsonify({'success': True, 'results': results})
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Xử lý quá thời gian cho phép'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<problem_id>', methods=['GET'])
def get_results(problem_id):
    """GET /api/results/P001 - Lấy kết quả phân loại + feedback"""
    import re
    if not re.match(r'^[A-Za-z0-9_]+$', problem_id):
        return jsonify({'error': 'Invalid problem_id'}), 400
    try:
        results = {}
        
        # Lấy classification JSON mới nhất
        classification_dir = Path(os.path.join(PROJECT_ROOT, "auto_grader/output/classifications"))
        if classification_dir.exists():
            json_files = list(classification_dir.glob("*.json"))
            if json_files:
                latest = max(json_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['classification'] = json.load(f)
        
        # Lấy feedback JSON
        feedback_dir = Path(os.path.join(PROJECT_ROOT, "auto_grader/output/feedback"))
        if feedback_dir.exists():
            feedback_files = list(feedback_dir.glob("*{}*.json".format(problem_id)))
            if feedback_files:
                latest = max(feedback_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['feedback'] = json.load(f)
        
        # Lấy loop history
        history_dir = Path(os.path.join(PROJECT_ROOT, "auto_grader/output/auto_fix_history"))
        if history_dir.exists():
            history_files = list(history_dir.glob("{}_*.json".format(problem_id)))
            if history_files:
                latest = max(history_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['loop_history'] = json.load(f)
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """GET /api/metrics - Tải CSV metrics"""
    try:
        metrics_file = os.path.join(PROJECT_ROOT, "auto_grader/output/metrics.csv")
        if not os.path.exists(metrics_file):
            return jsonify({'error': 'Metrics not found'}), 404
        
        return send_file(metrics_file, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)