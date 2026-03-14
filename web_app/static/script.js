const API_BASE = 'http://localhost:5000/api';
let problems = [];
let selectedProblem = null;

window.addEventListener('DOMContentLoaded', () => {
    loadProblems();
});

async function loadProblems() {
    try {
        const response = await fetch(`${API_BASE}/problems`);
        const data = await response.json();
        
        // API returns {P001: {...}, P002: {...}} object
        problems = Object.entries(data).map(([id, info]) => ({
            id: id,
            title: info.title,
            description: info.description,
            difficulty: info.difficulty || 'Easy'
        }));
        renderProblems();
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('problemList').innerHTML = '<p>Lỗi tải danh sách bài tập</p>';
    }
}

function renderProblems() {
    const list = document.getElementById('problemList');
    
    list.innerHTML = problems.map(p => `
        <div class="problem-item" onclick="selectProblem('${p.id}')">
            <div><strong>${p.id}</strong></div>
            <div>${p.title}</div>
            ${p.difficulty ? `<span class="badge ${p.difficulty.toLowerCase()}">${p.difficulty}</span>` : ''}
        </div>
    `).join('');
}

function selectProblem(id) {
    selectedProblem = problems.find(p => p.id === id);
    
    document.querySelectorAll('.problem-item').forEach(el => {
        el.classList.remove('active');
    });
    event.target.closest('.problem-item').classList.add('active');
    
    document.getElementById('problemView').innerHTML = `
        <h2>${selectedProblem.title}</h2>
        <p>${selectedProblem.description}</p>
        <textarea id="codeEditor" placeholder="Viết code..."></textarea>
        <button onclick="submitCode()" id="submitBtn">✅ Submit</button>
        <div id="result"></div>
    `;
}

async function submitCode() {
    const code = document.getElementById('codeEditor').value;
    
    if (!code.trim()) {
        alert('Vui lòng nhập code!');
        return;
    }

    showLoading(true);

    try {
        const response = await fetch(`${API_BASE}/submit`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                problem_id: selectedProblem.id,
                student_id: 'SV001',
                code: code
            })
        });

        const data = await response.json();

        if (data.success) {
            showResult(data.result);
        }
    } catch (error) {
        alert('Lỗi: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function showResult(result) {
    const isPassed = result.loai_loi.toLowerCase().includes('pass');
    
    document.getElementById('result').innerHTML = `
        <div class="result ${isPassed ? 'success' : ''}">
            <h3>📊 Kết quả</h3>
            <p><strong>Loại lỗi:</strong> ${result.loai_loi}</p>
            <p><strong>Nguyên nhân:</strong> ${result.nguyen_nhan}</p>
            <p><strong>Gợi ý:</strong> ${result.goi_y}</p>
            
            ${!isPassed ? '<button onclick="getFeedback()" class="btn-secondary">💡 Xem gợi ý AI</button>' : ''}
        </div>
    `;
}

async function getFeedback() {
    showLoading(true);
    
    try {
        const response = await fetch(`${API_BASE}/feedback/${selectedProblem.id}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showFeedbackDetail(data.feedback);
        }
    } finally {
        showLoading(false);
    }
}

function showFeedbackDetail(feedback) {
    const html = `
        <div class="result" style="border-left-color: #667eea; margin-top: 1rem;">
            <h3>💡 Gợi ý chi tiết</h3>
            <p><strong>Giải thích:</strong> ${feedback.explanation || 'N/A'}</p>
            <p><strong>Hướng dẫn:</strong></p>
            <pre>${feedback.reasoning || 'N/A'}</pre>
        </div>
    `;
    
    document.getElementById('result').innerHTML += html;
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