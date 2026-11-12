// ─────────────────────────────────────────
//  LOGIN PAGE LOGIC
//  Face matching removed — sirf detection
// ─────────────────────────────────────────

let storedUsername = '';
let storedPassword = '';
let faceDetected = false;

function togglePassword() {
    const input = document.getElementById('password');
    const icon  = document.getElementById('eyeIcon');
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

function goBack() {
    stopCamera();
    showStep('credentials');
    faceDetected = false;
    capturedDescriptor = null;
    const btn = document.getElementById('verifyBtn');
    if (btn) btn.disabled = true;
}

function showStep(name) {
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    const el = document.getElementById(`step-${name}`);
    if (el) el.classList.add('active');
}

function showError(msg, step2 = false) {
    const id  = step2 ? 'errorMsg2'  : 'errorMsg';
    const tid = step2 ? 'errorText2' : 'errorText';
    const div = document.getElementById(id);
    const txt = document.getElementById(tid);
    if (div && txt) {
        txt.textContent = msg;
        div.style.display = 'flex';
        setTimeout(() => div.style.display = 'none', 5000);
    }
}

function hideError() {
    ['errorMsg','errorMsg2'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
}

// ── STEP 1: Credentials ──
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();

    if (!username || !password) {
        showError('Username aur password dono bharo!');
        return;
    }

    storedUsername = username;
    storedPassword = password;

    showStep('face');
    initFaceVerification();
});

// ── STEP 2: Face Detection ──
async function initFaceVerification() {
    const statusEl  = document.getElementById('faceStatus');
    const verifyBtn = document.getElementById('verifyBtn');

    statusEl.innerHTML   = '<i class="fas fa-spinner fa-spin"></i> Camera shuru ho rahi hai...';
    statusEl.className   = 'face-status';
    faceDetected         = false;
    capturedDescriptor   = null;
    if (verifyBtn) verifyBtn.disabled = true;

    await startFaceDetection(
        (descriptor) => {
            if (!faceDetected) {
                faceDetected = true;
                capturedDescriptor = descriptor;
                statusEl.innerHTML = '<i class="fas fa-circle-check"></i> Chehra detect ho gaya! Login karo.';
                statusEl.className = 'face-status success';
                if (verifyBtn) verifyBtn.disabled = false;
            }
        },
        (message) => {
            if (!faceDetected) {
                statusEl.innerHTML = message
                    ? `<i class="fas fa-triangle-exclamation"></i> ${message}`
                    : '<i class="fas fa-camera"></i> Camera ke saamne apna chehra lao...';
                statusEl.className = message ? 'face-status error' : 'face-status';
                if (verifyBtn) verifyBtn.disabled = true;
            }
        }
    );
}

// ── STEP 3: Login ──
async function verifyAndLogin() {
    if (!capturedDescriptor) {
        showError('Pehle apna chehra camera pe dikhao.', true);
        return;
    }

    showStep('loading');
    stopCamera();

    try {
        // Get GPS location
        let lat = null, lon = null;
        try {
            const pos = await getPosition();
            lat = pos.coords.latitude;
            lon = pos.coords.longitude;
        } catch (e) {
            console.warn('GPS not available:', e.message);
        }

        const result = await apiCall('/auth/login/', 'POST', {
            username:        storedUsername,
            password:        storedPassword,
            face_descriptor: descriptorToArray(capturedDescriptor),
            face_matched:    true,  // face detected = face present
            latitude:        lat,
            longitude:       lon,
        });

        if (result.success) {
            localStorage.setItem('employee',      JSON.stringify(result.employee));
            localStorage.setItem('attendance_id', result.attendance.id);
            window.location.href = 'dashboard.html';
        }
    } catch (err) {
        showStep('face');
        initFaceVerification();
        showError(err.error || 'Login failed. Dobara try karein.', true);
    }
}
