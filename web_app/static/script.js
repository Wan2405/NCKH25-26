// API base URL - sử dụng relative path để hoạt động cả khi deploy
const API_BASE = '/api';
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
        console.error('Error loading problems:', error);
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
    // Sử dụng data attribute an toàn hơn
    const items = document.querySelectorAll('.problem-item');
    items.forEach(el => {
        const strongEl = el.querySelector('strong');
        if (strongEl && strongEl.textContent === id) {
            el.classList.add('active');
        }
    });
    
    document.getElementById('problemView').innerHTML = `
        <h2>${selectedProblem.title}</h2>
        <p>${selectedProblem.description}</p>
        <textarea id="codeEditor" placeholder="Viết code Java tại đây..."></textarea>
        <button onclick="submitCode()" id="submitBtn">✅ Submit & Grade</button>
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
        // Gọi đúng endpoint /api/grade (không phải /api/submit)
        const response = await fetch(`${API_BASE}/grade`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                problem_id: selectedProblem.id,
                student_id: 'SV001',
                code: code
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showResult(data.results);
        } else {
            alert('Lỗi: ' + (data.error || 'Không xác định'));
        }
    } catch (error) {
        alert('Lỗi kết nối: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function showResult(results) {
    const classification = results.classification || {};
    const feedback = results.feedback || {};
    const classInfo = classification.classification || classification;
    
    const errorType = classInfo.loai_loi || 'Unknown';
    const isPassed = errorType.toUpperCase().includes('PASS');
    
    let html = `
        <div class="result ${isPassed ? 'success' : ''}">
            <h3>📊 Kết quả</h3>
            <p><strong>Loại lỗi:</strong> ${errorType}</p>
            <p><strong>Nguyên nhân:</strong> ${classInfo.nguyen_nhan || 'N/A'}</p>
            <p><strong>Gợi ý:</strong> ${classInfo.goi_y || 'N/A'}</p>
    `;
    
    // Hiển thị feedback nếu có
    if (feedback.explanation) {
        html += `
            <hr style="margin: 1rem 0;">
            <h3>💡 Gợi ý từ AI</h3>
            <p><strong>Giải thích:</strong> ${feedback.explanation}</p>
            <p><strong>Hướng dẫn:</strong></p>
            <pre>${feedback.reasoning || 'N/A'}</pre>
        `;
    }
    
    html += '</div>';
    document.getElementById('result').innerHTML = html;
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