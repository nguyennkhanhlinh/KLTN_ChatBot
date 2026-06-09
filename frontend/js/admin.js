const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://localhost:8000'
  : 'https://kltn-chatbot.onrender.com';

const token = localStorage.getItem('chatbot:token');
const role  = localStorage.getItem('chatbot:role');

if (!token) { window.location.replace('login.html'); }
if (role !== 'admin') { window.location.replace('index.html'); }


function authHeaders() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, { headers: authHeaders(), ...opts });
  if (res.status === 401) { localStorage.clear(); window.location.replace('login.html'); }
  return res;
}


const navItems = document.querySelectorAll('.admin-nav-item');
navItems.forEach(btn => {
  btn.addEventListener('click', () => {
    navItems.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.admin-tab').forEach(t => t.hidden = true);
    document.getElementById(`tab-${btn.dataset.tab}`).hidden = false;
    if (btn.dataset.tab === 'overview') loadStats();
    if (btn.dataset.tab === 'users')    loadUsers();
    if (btn.dataset.tab === 'sessions') loadSessions();
  });
});


/* ===================== DASHBOARD (Tổng quan) ===================== */

const DASH_ACCENT = '#1d4ed8';
const DASH_GREEN  = '#0f766e';
const DASH_GRID   = 'rgba(79,142,247,0.12)';
const DASH_TICK   = '#7a90b8';

function _dashLayout(title, extra = {}) {
  return {
    title: { text: title, font: { color: '#c8d8f0', size: 13 }, x: 0.02 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: DASH_TICK, size: 11 },
    margin: { l: 48, r: 18, t: 40, b: 48 },
    xaxis: { gridcolor: DASH_GRID, color: DASH_TICK, automargin: true },
    yaxis: { gridcolor: DASH_GRID, color: DASH_TICK, automargin: true },
    showlegend: false,
    ...extra,
  };
}

const _dashCfg = { responsive: true, displayModeBar: false };

async function loadStats() {
  const res = await apiFetch('/admin/stats');
  if (!res.ok) return;
  const s = await res.json();
  renderKpi(s.kpi);

  // So sánh model sử dụng (số phiên theo model)
  const mu = s.model_usage || [];
  Plotly.newPlot('chartUsersByDay', [{
    type: 'bar',
    x: mu.map(r => r[0]), y: mu.map(r => r[1]),
    marker: { color: DASH_ACCENT },
  }], _dashLayout('So sánh model sử dụng'), _dashCfg);

  // Phiên chat theo ngày
  Plotly.newPlot('chartSessionsByDay', [{
    type: 'scatter', mode: 'lines+markers',
    x: s.sessions_by_day.map(r => r[0]), y: s.sessions_by_day.map(r => r[1]),
    line: { color: DASH_GREEN, width: 2 }, marker: { color: DASH_GREEN, size: 6 },
    fill: 'tozeroy', fillcolor: 'rgba(15,118,110,0.45)',
  }], _dashLayout('Phiên chat theo ngày'), _dashCfg);

  // Top user theo số phiên (bar ngang, đảo để cao nhất ở trên)
  const tu = [...s.top_users].reverse();
  Plotly.newPlot('chartTopUsers', [{
    type: 'bar', orientation: 'h',
    y: tu.map(r => r[0]), x: tu.map(r => r[1]),
    marker: { color: DASH_ACCENT },
  }], _dashLayout('Top người dùng (theo số phiên)', { margin: { l: 90, r: 18, t: 40, b: 40 } }), _dashCfg);

  // Lý do không hài lòng (dislike có chọn lý do)
  const reasonLabels = {
    wrong_data: 'Sai số liệu', irrelevant: 'Không liên quan',
    incomplete: 'Thiếu thông tin', unclear: 'Khó hiểu', other: 'Khác',
  };
  const dr = s.dislike_reasons || [];
  Plotly.newPlot('chartRoleRatio', [{
    type: 'bar',
    x: dr.map(r => reasonLabels[r[0]] || r[0]), y: dr.map(r => r[1]),
    marker: { color: '#f87171' },
  }], _dashLayout('Lý do không hài lòng'), _dashCfg);

  // Phiên theo khung giờ (điền đủ 0–23h)
  const byHour = new Array(24).fill(0);
  s.sessions_by_hour.forEach(([h, c]) => { if (h >= 0 && h < 24) byHour[h] = c; });
  Plotly.newPlot('chartSessionsByHour', [{
    type: 'bar',
    x: byHour.map((_, h) => `${h}h`), y: byHour,
    marker: { color: DASH_GREEN },
  }], _dashLayout('Phiên theo khung giờ'), _dashCfg);
}

function renderKpi(k) {
  const cards = [
    { label: 'Người dùng',       value: k.total_users,    sub: `+${k.users_today} hôm nay` },
    { label: 'Phiên chat',       value: k.total_sessions, sub: `+${k.sessions_today} hôm nay` },
    { label: 'Lượt thích',       value: k.like_count,     sub: '' },
    { label: 'Lượt không thích', value: k.dislike_count,  sub: '' },
  ];
  document.getElementById('dashKpi').innerHTML = cards.map(c => `
    <div class="dash-kpi-card">
      <div class="dash-kpi-value">${(c.value || 0).toLocaleString('vi-VN')}</div>
      <div class="dash-kpi-label">${c.label}</div>
      ${c.sub ? `<div class="dash-kpi-sub">${c.sub}</div>` : ''}
    </div>`).join('');
}


async function loadUsers() {
  const res = await apiFetch('/admin/users');
  _allUsers = await res.json();
  renderUsers(_allUsers);
}

function renderUsers(users) {
  const tbody = document.getElementById('usersTableBody');
  const me    = localStorage.getItem('chatbot:username');
  tbody.innerHTML = users.length === 0
    ? '<tr><td colspan="6" class="table-empty">Chưa có người dùng nào.</td></tr>'
    : users.map(u => `
      <tr>
        <td><span class="user-name-cell">${u.username}</span>${u.username === me ? ' <span class="badge-you">bạn</span>' : ''}</td>
        <td><span class="password-hash">${u.password || '—'}</span></td>
        <td>${u.email || '—'}</td>
        <td>${u.phone || '—'}</td>
        <td><span class="role-badge role-${u.role}">${u.role}</span></td>
        <td>${u.created_at ? new Date(u.created_at).toLocaleString('vi-VN') : '—'}</td>
      </tr>`).join('');
}

document.getElementById('userFilterInput').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  renderUsers(q ? _allUsers.filter(u => u.username.toLowerCase().includes(q)) : _allUsers);
});



document.getElementById('createUserBtn').addEventListener('click', async () => {
  const username = document.getElementById('newUsername').value.trim();
  const password = document.getElementById('newPassword').value;
  const role     = document.getElementById('newRole').value;
  const errEl    = document.getElementById('createUserError');

  if (!username || !password) { errEl.textContent = 'Vui lòng nhập đầy đủ.'; errEl.hidden = false; return; }

  const res = await apiFetch('/admin/users', {
    method: 'POST',
    body: JSON.stringify({ username, password, role }),
  });
  if (!res.ok) {
    const d = await res.json();
    errEl.textContent = d.detail || 'Tạo thất bại.';
    errEl.hidden = false;
    return;
  }
  document.getElementById('newUsername').value = '';
  document.getElementById('newPassword').value = '';
  errEl.hidden = true;
  loadUsers();
});


let _allUsers = [];
let _allSessions = [];

async function loadSessions() {
  const res      = await apiFetch('/admin/sessions');
  _allSessions   = await res.json();
  renderSessions(_allSessions);
}

function renderSessions(sessions) {
  const tbody = document.getElementById('sessionsTableBody');
  tbody.innerHTML = sessions.length === 0
    ? '<tr><td colspan="3" class="table-empty">Chưa có cuộc trò chuyện nào.</td></tr>'
    : sessions.map(s => {
        const deletedBadge = s.is_deleted
          ? `<span class="badge-deleted" title="Người dùng đã xoá${s.deleted_at ? ' lúc ' + new Date(s.deleted_at).toLocaleString('vi-VN') : ''}">Đã xoá</span>`
          : '';
        return `
      <tr class="${s.is_deleted ? 'session-row-deleted' : ''}">
        <td>
          <span class="user-name-cell session-open-link" data-id="${s.id}" data-username="${s.username}" title="Xem lịch sử">${s.username}</span>
        </td>
        <td class="session-title-cell">${s.title}${deletedBadge}</td>
        <td>${s.created_at ? new Date(s.created_at).toLocaleString('vi-VN') : '—'}</td>
      </tr>`;
      }).join('');

  tbody.querySelectorAll('.session-open-link').forEach(el => {
    el.addEventListener('click', () => openSessionModal(el.dataset.id, el.dataset.username));
  });
}

function _renderModalChart(data, chartId) {
  const cols  = data.columns || [];
  const rows  = data.data    || [];
  const ctype = data.chart_type || 'bar';
  const n     = rows.length;

  const layout = {
    title: { text: data.title || '', font: { color: '#c8d8f0', size: 13 } },
    paper_bgcolor: '#030d22', plot_bgcolor: '#030d22',
    font: { color: '#7a90b8', size: 11 },
    xaxis: { gridcolor: 'rgba(79,142,247,0.1)', color: '#7a90b8', automargin: true,
             tickangle: (ctype === 'bar' && n > 8) ? -40 : 0,
             title: { text: ctype === 'horizontal_bar' ? (data.y_label||'') : (data.x_label||cols[0]||'') } },
    yaxis: { gridcolor: 'rgba(79,142,247,0.1)', color: '#7a90b8', automargin: true,
             title: { text: ctype === 'horizontal_bar' ? (data.x_label||'') : (data.y_label||'') } },
    margin: { l: ctype === 'horizontal_bar' ? 130 : 60, r: 24, t: data.title ? 44 : 20, b: ctype === 'bar' && n > 8 ? 100 : 60 },
    legend: { font: { color: '#c8d8f0' } },
  };

  let traces;
  if (ctype === 'pie') {
    traces = [{ type: 'pie', labels: rows.map(r => r[0]), values: rows.map(r => r[1]),
      textinfo: 'percent+label', marker: { line: { color: '#21262d', width: 1 } } }];
  } else if (ctype === 'scatter') {
    traces = cols.slice(1).map((name, i) => ({ type: 'scatter', mode: 'markers', name,
      x: rows.map(r => r[0]), y: rows.map(r => r[i+1]) }));
  } else if (ctype === 'line') {
    traces = cols.slice(1).map((name, i) => ({ type: 'scatter', mode: 'lines+markers', name,
      x: rows.map(r => r[0]), y: rows.map(r => r[i+1]) }));
  } else if (ctype === 'horizontal_bar') {
    traces = cols.slice(1).map((name, i) => ({ type: 'bar', orientation: 'h', name,
      y: rows.map(r => r[0]), x: rows.map(r => r[i+1]) }));
  } else {
    traces = cols.slice(1).map((name, i) => ({ type: 'bar', name,
      x: rows.map(r => r[0]), y: rows.map(r => r[i+1]) }));
    if (ctype === 'stacked_bar') layout.barmode = 'stack';
  }

  Plotly.newPlot(chartId, traces, layout, { responsive: true, displayModeBar: false });
}

async function openSessionModal(sessionId, username) {
  document.getElementById('sessionModalTitle').textContent = `Lịch sử — ${username}`;
  const body = document.getElementById('sessionModalBody');
  body.innerHTML = '<p class="session-modal-loading">Đang tải...</p>';
  document.getElementById('sessionModal').hidden = false;

  const res = await apiFetch(`/sessions/${encodeURIComponent(sessionId)}`);
  if (!res.ok) { body.innerHTML = '<p class="session-modal-loading">Lỗi tải dữ liệu.</p>'; return; }
  const { messages } = await res.json();

  if (!messages || messages.length === 0) {
    body.innerHTML = '<p class="session-modal-loading">Không có tin nhắn.</p>';
    return;
  }

  body.innerHTML = '';
  let chartIdx = 0;
  messages.forEach(m => {
    const div = document.createElement('div');
    if (m.role === 'chart') {
      const cid = `sm-chart-${++chartIdx}`;
      div.className = 'sm-msg sm-msg-bot sm-chart-wrap';
      div.innerHTML = `<div id="${cid}" style="width:100%;height:320px;"></div>`;
      body.appendChild(div);
      _renderModalChart(m.data, cid);
    } else {
      div.className = `sm-msg ${m.role === 'user' ? 'sm-msg-user' : 'sm-msg-bot'}`;
      div.textContent = m.content;
      body.appendChild(div);
    }
  });
}

document.getElementById('sessionModalClose').addEventListener('click', () => {
  document.getElementById('sessionModal').hidden = true;
});
document.getElementById('sessionModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) e.currentTarget.hidden = true;
});

document.getElementById('sessionFilterInput').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  renderSessions(q ? _allSessions.filter(s => s.username.toLowerCase().includes(q)) : _allSessions);
});


loadStats();

