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
    'P002': {'title': 'Tinh giai thua', 'description': 'Viet ham tinhGiaiThua(int n) tra ve n!'},
    'P003': {'title': 'Kiem tra so nguyen to', 'description': 'Viet ham kiemTraNguyenTo(int n) tra ve true neu n la so nguyen to'},
    'P004': {'title': 'Tim max trong mang', 'description': 'Viet ham timMax(int[] arr) tra ve phan tu lon nhat'},
    'P005': {'title': 'Dao nguoc chuoi', 'description': 'Viet ham daoNguoc(String s) tra ve chuoi dao nguoc'},
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
        
        if problem_id not in PROBLEMS:
            return jsonify({'error': 'Unknown problem: {}'.format(problem_id)}), 400
        
        # Tạo file code tạm
        temp_file = "auto_grader/input_code/{}_temp.java".format(problem_id)
        Path(temp_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Chạy runner - kiểm tra return code
        runner_result = subprocess.run(
            [sys.executable, 'runner.py', problem_id, temp_file, student_id],
            capture_output=True,
            text=True,
            timeout=180
        )
        if runner_result.returncode != 0:
            print("Runner stderr: {}".format(runner_result.stderr))
        
        # Chạy phân loại
        classify_result = subprocess.run(
            [sys.executable, 'phan_loai_loi.py'],
            capture_output=True,
            text=True,
            timeout=120
        )
        if classify_result.returncode != 0:
            print("Classifier stderr: {}".format(classify_result.stderr))
        
        # Chạy feedback
        feedback_result = subprocess.run(
            [sys.executable, 'tao_feedback.py', problem_id],
            capture_output=True,
            text=True,
            timeout=120
        )
        if feedback_result.returncode != 0:
            print("Feedback stderr: {}".format(feedback_result.stderr))
        
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
            files = list(feedback_dir.glob("*{}*.json".format(problem_id)))
            if files:
                latest = max(files, key=lambda x: x.stat().st_mtime)
                with open(latest, 'r', encoding='utf-8') as f:
                    results['feedback'] = json.load(f)
        
        return jsonify({'success': True, 'results': results})
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Xử lý quá thời gian cho phép'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)