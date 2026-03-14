// Auto Grader - simplified code submission
const API_BASE = '/api';

async function submitCode() {
    const code = document.getElementById('codeEditor').value.trim();

    if (!code) {
        alert('Please enter Java code.');
        return;
    }

    showLoading(true);

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code})
        });

        const data = await response.json();

        if (!response.ok) {
            alert('Error: ' + (data.error || 'Unknown error'));
            return;
        }

        showResult(data);
    } catch (error) {
        alert('Network error: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function showResult(data) {
    const status = data.status || 'unknown';
    const isPassed = status === 'success';

    const statusLabels = {
        'success':       '✅ SUCCESS',
        'compile_error': '❌ COMPILE ERROR',
        'runtime_error': '⚠️ RUNTIME ERROR',
        'timeout':       '⏱ TIMEOUT',
        'error':         '❌ ERROR'
    };

    let html = `<div class="result ${isPassed ? 'success' : ''}">
        <h3>📊 Result: ${statusLabels[status] || status.toUpperCase()}</h3>
        <p><strong>Class:</strong> ${data.class_name || 'unknown'}</p>`;

    if (data.compile_error) {
        html += `<hr style="margin:1rem 0">
        <p><strong>Compile Error:</strong></p>
        <pre>${escapeHtml(data.compile_error)}</pre>`;
    }

    if (data.stdout) {
        html += `<hr style="margin:1rem 0">
        <p><strong>Output:</strong></p>
        <pre>${escapeHtml(data.stdout)}</pre>`;
    }

    if (data.stderr && status !== 'compile_error') {
        html += `<hr style="margin:1rem 0">
        <p><strong>Runtime Error:</strong></p>
        <pre>${escapeHtml(data.stderr)}</pre>`;
    }

    html += '</div>';
    document.getElementById('result').innerHTML = html;
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function showLoading(show) {
    let spinner = document.getElementById('loadingSpinner');

    if (show && !spinner) {
        spinner = document.createElement('div');
        spinner.id = 'loadingSpinner';
        spinner.className = 'loading';
        spinner.innerHTML = '<div class="spinner"></div><p>Đang xử lý...</p>';
        document.body.appendChild(spinner);
    } else if (!show && spinner) {
        spinner.remove();
    }
}
