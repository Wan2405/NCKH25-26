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
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(__file__))
from runner import main as run_test
from run_feedback_loop import auto_fix_loop

app = Flask(__name__, template_folder='templates')
CORS(app)

PROBLEMS = {
    'P001': {
        'title': 'Tong hai so',
        'description': 'Viet ham tinhTong(int a, int b) tra ve tong a + b'
    },
    'P002': {
        'title': 'Tinh giai thua',
        'description': 'Viet ham tinhGiaiThua(int n) tra ve n!'
    }
}

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
        data = request.json
        problem_id = data.get('problem_id')
        code = data.get('code')
        student_id = data.get('student_id', 'SV001')
        use_docker = data.get('use_docker', True)
        use_feedback_loop = data.get('use_feedback_loop', False)
        max_rounds = data.get('max_rounds', 3)
        
        # Kiểm tra input
        if not problem_id or not code:
            return jsonify({'error': 'Missing problem_id or code'}), 400
        
        if problem_id not in PROBLEMS:
            return jsonify({'error': f'Unknown problem: {problem_id}'}), 400
        
        # Tạo file code tạm thời
        temp_code_dir = Path(f"auto_grader/input_code")
        temp_code_dir.mkdir(parents=True, exist_ok=True)
        
        temp_code_file = temp_code_dir / f"{problem_id}_Solution.java"
        with open(temp_code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Chạy test
        sys.argv = ["runner.py", problem_id, str(temp_code_file), "--student_id", student_id]
        test_result = run_test()
        
        result = {
            'problem_id': problem_id,
            'student_id': student_id,
            'test_result': test_result,
            'feedback_loop_result': None
        }
        
        # Chạy feedback loop (nếu request)
        if use_feedback_loop:
            loop_history = auto_fix_loop(problem_id, max_rounds)
            result['feedback_loop_result'] = loop_history
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<problem_id>', methods=['GET'])
def get_results(problem_id):
    """GET /api/results/P001 - Lấy kết quả phân loại + feedback"""
    try:
        results = {}
        
        # Lấy classification JSON mới nhất
        classification_dir = Path("auto_grader/output/classifications")
        if classification_dir.exists():
            json_files = list(classification_dir.glob("*.json"))
            if json_files:
                latest = max(json_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['classification'] = json.load(f)
        
        # Lấy feedback JSON
        feedback_dir = Path("auto_grader/output/feedback")
        if feedback_dir.exists():
            feedback_files = list(feedback_dir.glob(f"*{problem_id}*.json"))
            if feedback_files:
                latest = max(feedback_files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['feedback'] = json.load(f)
        
        # Lấy loop history
        history_dir = Path("auto_grader/output/auto_fix_history")
        if history_dir.exists():
            history_files = list(history_dir.glob(f"{problem_id}_*.json"))
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
        metrics_file = Path("auto_grader/output/metrics.csv")
        if not metrics_file.exists():
            return jsonify({'error': 'Metrics not found'}), 404
        
        return send_file(str(metrics_file), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)