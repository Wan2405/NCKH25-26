"""
FLASK WEB APP - Auto Grader Web Interface
Simplified architecture: code submission -> compile -> run -> return result
"""

import logging
import os
import sys

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# Add project root to sys.path so auto_grader package is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from auto_grader.modules.executor import execute  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')
CORS(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/execute', methods=['POST'])
def execute_code():
    """
    POST /api/execute
    Body: { "code": "<java source code>" }
    Returns compilation and runtime results.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400

        code = data.get('code', '').strip()
        if not code:
            return jsonify({'error': 'Missing code'}), 400

        logger.info("Received code submission (%d chars), executing...", len(code))
        result = execute(code)
        return jsonify(result)

    except Exception as e:
        logger.exception("Unexpected error in execute_code")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import os as _os
    debug = _os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=5000)
