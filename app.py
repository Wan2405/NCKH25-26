"""
FLASK WEB APP - Auto Grader
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import subprocess
import sys
from pathlib import Path
import json

app = Flask(__name__, template_folder='templates')
CORS(app)

PROBLEMS = {
    'P001': {'title': 'Tong hai so', 'description': 'Viet ham tinhTong(int a, int b) tra ve tong a + b'},
    'P002': {'title': 'Tinh giai thua', 'description': 'Viet ham tinhGiaiThua(int n) tra ve n!'}
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/problems', methods=['GET'])
def get_problems():
    return jsonify(PROBLEMS)

@app.route('/api/grade', methods=['POST'])
def grade():
    try:
        data = request.json
        problem_id = data.get('problem_id')
        code = data.get('code')
        student_id = data.get('student_id', 'SV001')
        
        if not problem_id or not code:
            return jsonify({'error': 'Missing fields'}), 400
        
        # Tạo file code tạm
        temp_file = f"auto_grader/input_code/{problem_id}_temp.java"
        Path(temp_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Chạy runner
        subprocess.run(
            ['python', 'runner.py', problem_id, temp_file, student_id],
            timeout=120
        )
        
        # Chạy phân loại
        subprocess.run(['python', 'phan_loai_loi.py'], timeout=60)
        
        # Chạy feedback
        subprocess.run(['python', 'tao_feedback.py', problem_id], timeout=60)
        
        # Lấy kết quả
        results = {}
        
        class_dir = Path("auto_grader/output/classifications")
        if class_dir.exists():
            files = list(class_dir.glob("*.json"))
            if files:
                latest = max(files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['classification'] = json.load(f)
        
        feedback_dir = Path("auto_grader/output/feedback")
        if feedback_dir.exists():
            files = list(feedback_dir.glob(f"*{problem_id}*.json"))
            if files:
                latest = max(files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['feedback'] = json.load(f)
        
        return jsonify({'success': True, 'results': results})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)