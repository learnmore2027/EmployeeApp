const API_BASE = 'https://employeeapp-production-61218222.up.railway.app/api';

function getCookie(name) {
    let v = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(c => {
            c = c.trim();
            if (c.startsWith(name + '=')) v = decodeURIComponent(c.slice(name.length + 1));
        });
    }
    return v;
}

async function apiCall(endpoint, method = 'GET', data = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        credentials: 'include',
    };
    if (data && method !== 'GET') opts.body = JSON.stringify(data);
    const res = await fetch(`${API_BASE}${endpoint}`, opts);
    const json = await res.json();
    if (!res.ok) throw { status: res.status, ...json };
    return json;
}

function showError(msg, containerId = 'errorMsg', textId = 'errorText') {
    const d = document.getElementById(containerId);
    const t = document.getElementById(textId);
    if (d && t) {
        t.textContent = msg;
        d.style.display = 'flex';
        setTimeout(() => d.style.display = 'none', 5000);
    }
}

function hideError(containerId = 'errorMsg') {
    const d = document.getElementById(containerId);
    if (d) d.style.display = 'none';
}

function formatTime(s) {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return [h, m, sec].map(v => String(v).padStart(2, '0')).join(':');
}

function formatMins(m) {
    const h = Math.floor(m / 60), min = Math.floor(m % 60);
    return h > 0 ? `${h}h ${min}m` : `${min}m`;
}

function getGreeting() {
    const h = new Date().getHours();
    return h < 12 ? 'Good Morning! ☀️' : h < 17 ? 'Good Afternoon! 🌤️' : 'Good Evening! 🌙';
}

// GPS helpers
function getPosition() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error('GPS not supported'));
        navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true, timeout: 10000, maximumAge: 0
        });
    });
}

function showToast(msg, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'circle-xmark' : type === 'warning' ? 'triangle-exclamation' : 'circle-info'}"></i> ${msg}`;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 400); }, 3500);
}
