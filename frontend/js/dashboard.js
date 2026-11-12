// ── CONFIG ───────────────────────────────────────────────────────────────────
const SHIFT_HOURS    = 8;
const MAX_BREAK_MINS = 60;
const SHIFT_SECS     = SHIFT_HOURS * 3600;
const GEO_INTERVAL   = 30000;

let employeeData = null, attendanceData = null;
let timerInterval = null, clockInterval = null, breakTimerInterval = null, geoInterval = null;
let loginTimestamp = null, breakStartTimestamp = null, totalBreakSeconds = 0;

// ── INIT ─────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const auth = await apiCall('/auth/check/');
        if (!auth.authenticated) { window.location.href = 'login.html'; return; }

        const adminLink = document.getElementById('adminLink');
        if (adminLink) adminLink.style.display = auth.is_admin ? 'flex' : 'none';

    } catch { window.location.href = 'login.html'; return; }

    await loadDashboard();
    startClock();
    loadHistory();
    startGeoWatch();
});

// ── LOAD ─────────────────────────────────────────────────────────────────────
async function loadDashboard() {
    try {
        const data = await apiCall('/dashboard/');
        employeeData   = data.employee;
        attendanceData = data.attendance;

        document.getElementById('navName').textContent   = employeeData.name;
        document.getElementById('navDept').textContent   = employeeData.department || 'Employee';
        document.getElementById('navAvatar').textContent = employeeData.name.charAt(0).toUpperCase();
        document.getElementById('welcomeMsg').textContent      = getGreeting();
        document.getElementById('welcomeSubtitle').textContent = `Welcome back, ${employeeData.name}! Have a productive day. 💪`;

        const lb = document.getElementById('leaveBalance');
        if (lb) lb.textContent = `${employeeData.leave_balance} days left`;

        if (attendanceData && attendanceData.login_time) {
            loginTimestamp = new Date(attendanceData.login_time);
            document.getElementById('loginTimeDisplay').textContent =
                loginTimestamp.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });

            totalBreakSeconds = Math.round((attendanceData.total_break_minutes || 0) * 60);

            if (attendanceData.on_break && attendanceData.break_start) {
                breakStartTimestamp = new Date(attendanceData.break_start);
                showBreakUI(true, attendanceData.break_type);
                startBreakTimer();
            }
            startShiftTimer();
        }

        if (attendanceData && attendanceData.break_violation) {
            showViolationBanner(attendanceData.break_violation_minutes);
        }

        if (attendanceData) {
            window._officeLat    = attendanceData.office_lat;
            window._officeLon    = attendanceData.office_lon;
            window._officeRadius = attendanceData.office_radius;
        }

    } catch (err) {
        if (err.status === 401 || err.status === 403) window.location.href = 'login.html';
    }
}

// ── CLOCK ─────────────────────────────────────────────────────────────────────
function startClock() {
    const tick = () => {
        const now = new Date();
        document.getElementById('currentTime').textContent =
            now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
        document.getElementById('currentDate').textContent =
            now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    };
    tick(); clockInterval = setInterval(tick, 1000);
}

// ── SHIFT TIMER ───────────────────────────────────────────────────────────────
function startShiftTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        if (!loginTimestamp) return;
        const now       = new Date();
        const elapsed   = Math.floor((now - loginTimestamp) / 1000);
        const curBreak  = breakStartTimestamp ? Math.floor((now - breakStartTimestamp) / 1000) : 0;
        const breakSecs = totalBreakSeconds + curBreak;
        const workSecs  = Math.max(0, elapsed - breakSecs);

        document.getElementById('shiftTimer').textContent = formatTime(workSecs);

        const shiftPct = Math.min(100, (workSecs / SHIFT_SECS) * 100);
        document.getElementById('shiftProgress').style.width   = shiftPct + '%';
        document.getElementById('progressPercent').textContent = Math.round(shiftPct) + '%';
        document.getElementById('workHoursDisplay').textContent = formatMins(Math.floor(workSecs / 60));

        const breakMins = Math.floor(breakSecs / 60);
        const breakPct  = Math.min(100, (breakMins / MAX_BREAK_MINS) * 100);
        document.getElementById('breakProgress').style.width  = breakPct + '%';
        document.getElementById('breakPercent').textContent   = Math.round(breakPct) + '%';
        document.getElementById('breakTimeDisplay').textContent = `${breakMins}m / ${MAX_BREAK_MINS}m`;

        const hours = workSecs / 3600;
        const badge = hours >= SHIFT_HOURS ? 'present' : hours >= SHIFT_HOURS / 2 ? 'half_day' : 'absent';
        const label = { present: 'Full Day', half_day: 'Half Day', absent: 'In Progress' };
        document.getElementById('statusDisplay').innerHTML =
            `<span class="badge badge-${badge}">${label[badge]}</span>`;

        if (breakMins > MAX_BREAK_MINS) showViolationBanner(breakMins - MAX_BREAK_MINS);
    }, 1000);
}

// ── GEO WATCH ────────────────────────────────────────────────────────────────
function startGeoWatch() {
    if (!window._officeLat) return;
    const ping = async () => {
        try {
            const pos = await getPosition();
            const res = await apiCall('/geo/ping/', 'POST', {
                latitude:  pos.coords.latitude,
                longitude: pos.coords.longitude,
            });

            updateGeoStatus(res.inside, res.distance_m);

            if (res.action === 'break_started') {
                breakStartTimestamp = new Date();
                showBreakUI(true, 'geo');
                startBreakTimer();
                showToast('📍 Left office boundary — Break started automatically!', 'warning');
            } else if (res.action === 'break_ended') {
                totalBreakSeconds += breakStartTimestamp
                    ? Math.floor((new Date() - breakStartTimestamp) / 1000) : 0;
                breakStartTimestamp = null;
                showBreakUI(false);
                stopBreakTimer();
                showToast('✅ Back in office — Break ended!', 'success');
                await loadDashboard();
            }
        } catch (e) { console.warn('Geo ping failed:', e); }
    };
    ping();
    geoInterval = setInterval(ping, GEO_INTERVAL);
}

function updateGeoStatus(inside, distM) {
    const el = document.getElementById('geoStatus');
    if (!el) return;
    if (inside) {
        el.innerHTML  = `<i class="fas fa-location-dot"></i> Inside office <span class="geo-dist">${distM}m</span>`;
        el.className  = 'geo-status geo-inside';
    } else {
        el.innerHTML  = `<i class="fas fa-location-dot"></i> Outside office <span class="geo-dist">${distM}m</span>`;
        el.className  = 'geo-status geo-outside';
    }
}

// ── BREAK ─────────────────────────────────────────────────────────────────────
async function startBreak() {
    try {
        const res = await apiCall('/break/start/', 'POST');
        breakStartTimestamp = new Date(res.break_start);
        showBreakUI(true, 'manual');
        startBreakTimer();
        showToast(`☕ Break started! ${Math.round(res.remaining_minutes)} min remaining.`, 'info');
    } catch (err) { showToast(err.error || 'Could not start break.', 'error'); }
}

async function endBreak() {
    try {
        const res = await apiCall('/break/end/', 'POST');
        totalBreakSeconds += Math.round(parseFloat(res.duration_minutes) * 60);
        breakStartTimestamp = null;
        showBreakUI(false);
        stopBreakTimer();
        if (res.is_violation) {
            showViolationBanner(res.violation_minutes);
            showToast(`⚠️ Break limit exceeded by ${res.violation_minutes} min!`, 'warning');
        } else {
            showToast('✅ Break ended. Back to work!', 'success');
        }
    } catch (err) { showToast(err.error || 'Could not end break.', 'error'); }
}

function showBreakUI(onBreak, type = 'manual') {
    document.getElementById('breakStatusBanner').style.display = onBreak ? 'flex' : 'none';
    document.getElementById('breakStartBtn').style.display     = onBreak ? 'none' : 'flex';
    document.getElementById('breakEndBtn').style.display       = onBreak ? 'flex' : 'none';
    const badge = document.getElementById('breakTypeBadge');
    if (badge) badge.textContent = type === 'geo' ? '📍 Auto (Geo-fence)' : '✋ Manual';
}

function startBreakTimer() {
    if (breakTimerInterval) clearInterval(breakTimerInterval);
    breakTimerInterval = setInterval(() => {
        if (!breakStartTimestamp) return;
        const s  = Math.floor((new Date() - breakStartTimestamp) / 1000);
        const el = document.getElementById('breakTimer');
        if (el) el.textContent = `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
    }, 1000);
}

function stopBreakTimer() {
    if (breakTimerInterval) { clearInterval(breakTimerInterval); breakTimerInterval = null; }
}

function showViolationBanner(mins) {
    const el = document.getElementById('violationBanner');
    if (el) {
        el.innerHTML   = `<i class="fas fa-triangle-exclamation"></i> Break violation! <strong>${mins} min</strong> over the allowed limit.`;
        el.style.display = 'flex';
    }
}

// ── LOGOUT ───────────────────────────────────────────────────────────────────
function handleLogout() { document.getElementById('logoutModal').style.display = 'flex'; }
function closeModal()   { document.getElementById('logoutModal').style.display = 'none'; }

async function confirmLogout() {
    closeModal();
    if (geoInterval) clearInterval(geoInterval);
    try {
        const res = await apiCall('/auth/logout/', 'POST');
        if (res.success && res.summary) showSummaryModal(res.summary);
        else window.location.href = 'login.html';
    } catch (err) { showToast(err.error || 'Logout failed.', 'error'); }
}

function showSummaryModal(s) {
    [timerInterval, clockInterval, breakTimerInterval].forEach(t => t && clearInterval(t));
    const badges = {
        present:  '<span class="badge badge-present">Present ✅</span>',
        half_day: '<span class="badge badge-half_day">Half Day ⚠️</span>',
        absent:   '<span class="badge badge-absent">Absent ❌</span>',
    };
    const violation = s.break_violation
        ? `<div class="summary-row"><span class="label">⚠️ Break Violation</span><span class="value" style="color:#fdba74">+${s.break_violation_minutes} min over</span></div>` : '';
    document.getElementById('summaryContent').innerHTML = `
        <div class="summary-row"><span class="label">📅 Date</span><span class="value">${s.date}</span></div>
        <div class="summary-row"><span class="label">🟢 Login Time</span><span class="value">${s.login_time}</span></div>
        <div class="summary-row"><span class="label">🔴 Logout Time</span><span class="value">${s.logout_time}</span></div>
        <div class="summary-row"><span class="label">⏱️ Work Hours</span><span class="value">${s.total_work_hours.toFixed(2)} hrs</span></div>
        <div class="summary-row"><span class="label">☕ Break Hours</span><span class="value">${s.total_break_hours.toFixed(2)} hrs</span></div>
        ${violation}
        <div class="summary-row"><span class="label">📊 Status</span><span class="value">${badges[s.status] || s.status}</span></div>
    `;
    document.getElementById('summaryModal').style.display = 'flex';
}

// ── HISTORY ───────────────────────────────────────────────────────────────────
async function loadHistory() {
    const tbody = document.getElementById('historyTableBody');
    try {
        const res = await apiCall('/attendance/history/');
        if (!res.history.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-row">No records found.</td></tr>';
            return;
        }
        tbody.innerHTML = res.history.map(a => `
            <tr>
                <td>${new Date(a.date).toLocaleDateString('en-US', { day:'2-digit', month:'short', year:'numeric' })}</td>
                <td>${a.login_time}</td>
                <td>${a.logout_time}</td>
                <td>${a.work_hours.toFixed(1)}h</td>
                <td>${a.break_violation
                    ? `<span style="color:#fdba74">⚠️ +${a.violation_minutes}m</span>`
                    : `${(a.break_hours * 60).toFixed(0)}m`}</td>
                <td><span class="badge badge-${a.status}">${
                    { present:'Present', absent:'Absent', half_day:'Half Day', on_leave:'On Leave' }[a.status] || a.status
                }</span></td>
            </tr>
        `).join('');
    } catch {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-row">Failed to load history.</td></tr>';
    }
}
