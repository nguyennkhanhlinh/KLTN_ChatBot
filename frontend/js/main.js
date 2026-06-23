const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://localhost:8000'
  : 'https://kltn-chatbot-vpqm.onrender.com';

const _token = localStorage.getItem('chatbot:token');
if (!_token) { window.location.replace('login.html'); }

function authHeaders(extra = {}) {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${_token}`, ...extra };
}

function handleUnauthorized() {
  localStorage.clear();
  window.location.replace('login.html');
}


const _username = localStorage.getItem('chatbot:username') || '';
const _role     = localStorage.getItem('chatbot:role') || 'user';
document.getElementById('sidebarUserName').textContent = _username;
document.getElementById('sidebarUserRole').textContent = _role;
document.getElementById('sidebarUserAvatar').textContent = _username.charAt(0).toUpperCase() || 'U';

if (_role === 'admin') document.getElementById('adminPageBtn').hidden = false;



const _headerUserBtn      = document.getElementById('headerUserBtn');
const _headerUserDropdown = document.getElementById('headerUserDropdown');

_headerUserBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  _headerUserDropdown.hidden = !_headerUserDropdown.hidden;
});

document.addEventListener('click', () => { _headerUserDropdown.hidden = true; });

document.getElementById('logoutBtn').addEventListener('click', () => {
  localStorage.clear();
  window.location.replace('login.html');
});


const _profileModal = document.getElementById('profileModal');

document.getElementById('profileBtn').addEventListener('click', async () => {
  _headerUserDropdown.hidden = true;
  _profileModal.hidden = false;
  try {
    const res = await fetch(`${API}/auth/me`, { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return; }
    const d = await res.json();
    document.getElementById('profileUsername').textContent  = d.username || '—';
    document.getElementById('profileCreatedAt').textContent = d.created_at ? new Date(d.created_at).toLocaleString('vi-VN') : '—';

    const emailField = document.getElementById('profileEmail').closest('.profile-field');
    const phoneField = document.getElementById('profilePhone').closest('.profile-field');
    if (d.role === 'user' && d.email) { document.getElementById('profileEmail').textContent = d.email; emailField.hidden = false; }
    else { emailField.hidden = true; }
    if (d.role === 'user' && d.phone) { document.getElementById('profilePhone').textContent = d.phone; phoneField.hidden = false; }
    else { phoneField.hidden = true; }
  } catch { /* ignore */ }
});

document.getElementById('profileModalClose').addEventListener('click', () => { _profileModal.hidden = true; });
_profileModal.addEventListener('click', (e) => { if (e.target === _profileModal) _profileModal.hidden = true; });


const MODELS = [
  { id: 'gpt-4.1-mini',               label: 'GPT-4.1 Mini' },
  { id: 'o4-mini',                    label: 'O4 Mini' },
  { id: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  { id: 'mistralai/mistral-small-2603', label: 'Mistral Small 4' },
];
let selectedModel = localStorage.getItem('chatbot:model') || 'gpt-4.1-mini';
if (!MODELS.some(m => m.id === selectedModel)) {
  selectedModel = 'gpt-4.1-mini';
  localStorage.setItem('chatbot:model', selectedModel);
}

const modelSelectorBtn = document.getElementById('modelSelectorBtn');
const modelDropdown    = document.getElementById('modelDropdown');
const modelLabel       = document.getElementById('modelLabel');

function applyModelSelection(modelId) {
  selectedModel = modelId;
  localStorage.setItem('chatbot:model', modelId);
  const m = MODELS.find(x => x.id === modelId);
  modelLabel.textContent = m ? m.label : modelId;
  document.querySelectorAll('.model-dropdown-item').forEach(el => {
    el.classList.toggle('selected', el.dataset.model === modelId);
  });
}

modelSelectorBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  const isOpen = !modelDropdown.hidden;
  modelDropdown.hidden = isOpen;
  modelSelectorBtn.classList.toggle('open', !isOpen);
});

modelDropdown.addEventListener('click', (e) => {
  const item = e.target.closest('.model-dropdown-item');
  if (!item) return;
  applyModelSelection(item.dataset.model);
  modelDropdown.hidden = true;
  modelSelectorBtn.classList.remove('open');
});
document.addEventListener('click', (e) => {
  if (!modelSelectorBtn.contains(e.target) && !modelDropdown.contains(e.target)) {
    modelDropdown.hidden = true;
    modelSelectorBtn.classList.remove('open');
  }
});

applyModelSelection(selectedModel);

// Set current date
const dateEl = document.getElementById('current-date');
const now = new Date();
const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
dateEl.textContent = now.toLocaleDateString('vi-VN', opts);


// Sidebar collapse / open
const sidebar = document.getElementById('sidebar');
const openBtn  = document.getElementById('openBtn');

document.getElementById('collapseBtn').addEventListener('click', () => {
  sidebar.classList.add('collapsed');
  openBtn.style.display = 'flex';
});

openBtn.addEventListener('click', () => {
  sidebar.classList.remove('collapsed');
  openBtn.style.display = 'none';
});

// Auto-resize textarea + character counter
const chatInput = document.getElementById('chatInput');
const inputCounter = document.getElementById('inputCounter');
const sendBtn = document.getElementById('sendBtn');
const inputWrapper = document.querySelector('.input-wrapper');
const MAX_INPUT = parseInt(chatInput.getAttribute('maxlength'), 10) || 1000;

function updateCounter() {
  const len = chatInput.value.length;
  inputCounter.textContent = `${len}/${MAX_INPUT}`;
  inputCounter.classList.toggle('near-limit', len >= MAX_INPUT * 0.9);
  inputCounter.classList.toggle('at-limit', len >= MAX_INPUT);
  
  // Update input wrapper visual feedback
  inputWrapper.classList.toggle('near-limit', len >= MAX_INPUT * 0.9);
  inputWrapper.classList.toggle('at-limit', len >= MAX_INPUT);
  
  // Disable send button if empty or at max limit
  sendBtn.disabled = len === 0 || len >= MAX_INPUT;
}

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
  updateCounter();
});

chatInput.addEventListener('focus', () => {
  inputCounter.classList.add('visible');
});

chatInput.addEventListener('blur', () => {
  inputCounter.classList.remove('visible');
});

updateCounter();

// Fill input from quick actions
function fillInput(text) {
  chatInput.value = text;
  chatInput.focus();
  chatInput.dispatchEvent(new Event('input'));
}

// Send on Enter (Shift+Enter = newline)
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
document.getElementById('sendBtn').addEventListener('click', sendMessage);

const chatArea = document.getElementById('chatArea');
const welcomeScreen = document.getElementById('welcomeScreen');
const messagesContainer = document.getElementById('messagesContainer');
const historyList = document.getElementById('historyList');

// Chat sessions
let sessions = [];
let activeId = null;

function newSession(title) {
  const id = String(Date.now());
  sessions.unshift({ id, title, messages: [], createdAt: new Date() });
  activeId = id;
  renderHistoryList();
  return id;
}

// Load tất cả sessions đã lưu trong Postgres
async function loadSessionsFromBackend() {
  try {
    const res = await fetch(`${API}/sessions`, { headers: authHeaders() });
    if (res.status === 401) { handleUnauthorized(); return; }
    const data = await res.json();
    sessions = data.map(s => ({
      id: String(s.id),
      title: s.title,
      createdAt: s.createdAt ? new Date(Number(s.createdAt)) : null,
      messages: (s.messages || []).map(m => {
        if (m.role === 'chart') return { role: 'chart', data: m.data };
        return { role: m.role, html: m.content };
      }),
    }));
    renderHistoryList();
  } catch (e) {
    console.error('Không load được lịch sử từ backend:', e);
  }
}

function formatTime(date) {
  if (!date || Number.isNaN(date.getTime())) return '--:--';
  const d = new Date(date);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

function getDayLabel(date) {
  if (!date || Number.isNaN(date.getTime())) return 'Không rõ ngày';
  const d = new Date(date);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const toKey = x => `${x.getFullYear()}-${x.getMonth()}-${x.getDate()}`;
  if (toKey(d) === toKey(today)) return 'Hôm nay';
  if (toKey(d) === toKey(yesterday)) return 'Hôm qua';
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function renderHistoryList() {
  if (sessions.length === 0) {
    historyList.innerHTML = '<p class="history-empty">Chưa có cuộc trò chuyện nào.</p>';
    return;
  }

  const sortedSessions = [...sessions].sort((a, b) => {
    if (a.createdAt && b.createdAt) return b.createdAt - a.createdAt;
    if (a.createdAt) return -1;
    if (b.createdAt) return 1;
    return 0;
  });

  const groups = {};
  sortedSessions.forEach(s => {
    const label = getDayLabel(s.createdAt);
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  });

  let html = '';
  for (const [label, list] of Object.entries(groups)) {
    html += `<div class="history-group-label">${label}</div>`;
    html += list.map(s => `
      <div class="history-item-wrap">
        <button class="history-item ${s.id === activeId ? 'active' : ''}" data-id="${s.id}">
          <svg viewBox="0 0 24 24" width="13" height="13"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <div class="history-item-content">
            <span class="history-item-time"><svg viewBox="0 0 24 24" width="11" height="11" style="stroke:#fff;fill:none;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;vertical-align:middle;margin-right:3px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>${formatTime(s.createdAt)}</span>
            <span class="history-item-title">${s.title}</span>
          </div>
        </button>
        <div class="session-menu-wrap">
          <button class="session-menu-btn" data-menu="${s.id}" title="Tùy chọn">•••</button>
          <div class="session-dropdown" id="dropdown-${s.id}" hidden>
            <button class="session-dropdown-item session-dropdown-delete" data-del="${s.id}">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              Xóa
            </button>
          </div>
        </div>
      </div>`).join('');
  }
  historyList.innerHTML = html;
  
  historyList.removeEventListener('click', handleHistoryClick);
  historyList.addEventListener('click', handleHistoryClick);
}

function _closeAllDropdowns() {
  document.querySelectorAll('.session-dropdown').forEach(d => d.hidden = true);
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.session-menu-wrap')) _closeAllDropdowns();
});

// Event delegation handler for history items and delete buttons
function handleHistoryClick(e) {
  // 3-dot menu toggle
  const menuBtn = e.target.closest('.session-menu-btn');
  if (menuBtn) {
    e.stopPropagation();
    const id = menuBtn.dataset.menu;
    const dropdown = document.getElementById(`dropdown-${id}`);
    const isOpen = !dropdown.hidden;
    _closeAllDropdowns();
    if (!isOpen) {
      const rect = menuBtn.getBoundingClientRect();
      dropdown.style.top  = `${rect.bottom + 4}px`;
      dropdown.style.left = `${rect.left}px`;
      dropdown.hidden = false;
    }
    return;
  }

  // Xóa
  const deleteBtn = e.target.closest('[data-del]');
  if (deleteBtn) {
    (async () => {
      const id = deleteBtn.dataset.del;
      try {
        await fetch(`${API}/sessions/${encodeURIComponent(id)}`, {
          method: 'DELETE',
          headers: authHeaders(),
        });
      } catch (err) {
        console.error('Không xoá được session ở backend:', err);
        return;
      }
      sessions = sessions.filter(s => s.id !== id);
      if (activeId === id) {
        activeId = null;
        messagesContainer.innerHTML = '';
        chatArea.classList.add('welcome-mode');
      }
      renderHistoryList();
    })();
    return;
  }

  const historyItem = e.target.closest('.history-item');
  if (historyItem) {
    loadSession(historyItem.dataset.id);
    return;
  }
}

function loadSession(id) {
  const s = sessions.find(x => x.id === String(id));
  if (!s) return;
  activeId = s.id;
  messagesContainer.innerHTML = '';
  s.messages.forEach(m => {
    if (m.role === 'chart') _renderChart(m.data);
    else _renderMessage(m.role, m.html, m.role === 'bot');
  });
  chatArea.classList.remove('welcome-mode');
  renderHistoryList();
  _restoreFeedback(s.id);
}

// Tô lại màu like/dislike đã lưu cho phiên (sau khi đã render xong messages)
async function _restoreFeedback(sessionId) {
  try {
    const res = await fetch(`${API}/feedback/${encodeURIComponent(sessionId)}`, { headers: authHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    for (const fb of data.feedback || []) {
      const bar = document.querySelector(`.msg-actions[data-key="${fb.msg_key}"]`);
      if (!bar) continue;
      if (fb.rating === 'like') bar.querySelector('.msg-like')?.classList.add('active');
      else if (fb.rating === 'dislike') bar.querySelector('.msg-dislike')?.classList.add('active');
    }
  } catch (e) { /* im lặng */ }
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  if (!activeId || !sessions.find(s => s.id === activeId)) {
    newSession(text.slice(0, 42) + (text.length > 42 ? '…' : ''));
  }

  chatArea.classList.remove('welcome-mode');
  appendUserMessage(text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  updateCounter();

  const thinkingId = appendThinking();

  try {
    const res = await fetch(`${API}/chat/stream`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ question: text, session_id: String(activeId), model: selectedModel }),
    });
    if (res.status === 401) { handleUnauthorized(); return; }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split('\n\n');
      buffer = parts.pop();

      for (const part of parts) {
        for (const line of part.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          let data;
          try { data = JSON.parse(line.slice(6)); } catch { continue; }

          if (data.type === 'step') {
            addStepToThinking(thinkingId, data.label);
          } else if (data.type === 'done') {
            removeThinking(thinkingId);
            const payload = data.result;
            if (payload.type === 'chart') {
              appendChart(payload.data);
            } else if (payload.type === 'mixed') {
              const s = sessions.find(x => x.id === activeId);
              if (s) s.messages.push({ role: 'chart', data: payload.chart });
              appendChart(payload.chart, true);
              await typeBotMessage(payload.text || '');
            } else {
              await typeBotMessage(payload.content || '');
            }
          } else if (data.type === 'error') {
            removeThinking(thinkingId);
            appendBotMessage(`<span style="color:#ff5555">Lỗi: ${data.message}</span>`);
          }
        }
      }
    }
  } catch (err) {
    removeThinking(thinkingId);
    appendBotMessage(`<span style="color:#ff5555">Lỗi kết nối backend: ${err.message}</span>`);
  }
}

function appendUserMessage(text) {
  const s = sessions.find(x => x.id === activeId);
  if (s) s.messages.push({ role: 'user', html: text });
  _renderMessage('user', text);
}

function appendBotMessage(html) {
  const s = sessions.find(x => x.id === activeId);
  if (s) s.messages.push({ role: 'bot', html });
  _renderMessage('bot', html, true);
}

function typeBotMessage(rawText, charsPerTick = 2, intervalMs = 15) {
  rawText = String(rawText || '').trim();
  if (!rawText) {
    appendBotMessage('Mình chưa có câu trả lời phù hợp.');
    return Promise.resolve();
  }

  return new Promise(resolve => {
    const div = document.createElement('div');
    div.className = 'message bot-message';
    const avatarBot = `<div class="msg-avatar bot-avatar"><img src="../assets/images/robot.png" alt="Bot" /></div>`;
    const key = _nextMsgKey();
    div.innerHTML = `${avatarBot}<div class="msg-col"><div class="message-bubble"><span class="stream-text"></span><span class="stream-cursor">▍</span></div></div>`;
    messagesContainer.appendChild(div);
    const textEl = div.querySelector('.stream-text');
    const cursorEl = div.querySelector('.stream-cursor');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    let i = 0;
    const finalHtml = parseMarkdown(rawText);
    const id = setInterval(() => {
      i = Math.min(rawText.length, i + charsPerTick);
      textEl.innerHTML = parseMarkdown(rawText.slice(0, i));
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
      if (i >= rawText.length) {
        clearInterval(id);
        textEl.innerHTML = finalHtml;
        cursorEl.remove();
        div.querySelector('.msg-col').insertAdjacentHTML('beforeend', _botActions(key));
        const s = sessions.find(x => x.id === activeId);
        if (s) s.messages.push({ role: 'bot', html: finalHtml });
        resolve();
      }
    }, intervalMs);
  });
}

function parseMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
    .replace(/(\d+)\.\s+\*\*(.*?)\*\*/g, '<strong>$1. $2</strong>')
    .replace(/(\d+)\.\s+/g, '$1. ')
    .replace(/[-•]\s+/g, '&nbsp;&nbsp;• ');
}

// Định danh tin nhắn để gắn feedback: session hiện tại + chỉ số theo thứ tự DOM
function _nextMsgKey() {
  return `${activeId}#${messagesContainer.querySelectorAll('.message').length}`;
}

const FB_REASONS = [
  { code: 'wrong_data',  label: 'Sai số liệu' },
  { code: 'irrelevant',  label: 'Không liên quan' },
  { code: 'incomplete',  label: 'Thiếu thông tin' },
  { code: 'unclear',     label: 'Khó hiểu' },
];

const _ICON_COPY = `<svg class="icon-copy" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg><svg class="icon-check" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
const _ICON_LIKE = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>`;
const _ICON_DISLIKE = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>`;

const _COPY_BTN = `<button class="msg-action msg-copy" title="Sao chép" onclick="
  const el = this.closest('.msg-col').querySelector('.message-bubble');
  const text = el ? el.innerText.trim() : '';
  navigator.clipboard.writeText(text).then(() => { this.classList.add('copied'); setTimeout(() => this.classList.remove('copied'), 1500); });
">${_ICON_COPY}</button>`;

// firstBtn: nút copy (text) hoặc nút tải ảnh (chart). msgKey: định danh tin.
function _actionBar(msgKey, firstBtn) {
  return `<div class="msg-actions" data-key="${msgKey}">
    ${firstBtn}
    <button class="msg-action msg-like" title="Hữu ích" onclick="_fbLike(this)">${_ICON_LIKE}</button>
    <button class="msg-action msg-dislike" title="Chưa tốt" onclick="_fbDislike(this)">${_ICON_DISLIKE}</button>
  </div>`;
}

function _botActions(msgKey) { return _actionBar(msgKey, _COPY_BTN); }

// Gửi feedback lên backend (rating=null để bỏ đánh giá). Im lặng nếu lỗi.
function _sendFeedback(msgKey, rating, reason = null, comment = null) {
  fetch(`${API}/feedback`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ session_id: String(activeId), msg_key: msgKey, rating, reason, comment }),
  }).catch(() => {});
}

function _fbLike(btn) {
  const bar = btn.closest('.msg-actions');
  const key = bar.dataset.key;
  const like = bar.querySelector('.msg-like');
  const dislike = bar.querySelector('.msg-dislike');
  _closeReasons(bar);
  if (like.classList.contains('active')) {
    like.classList.remove('active');
    _sendFeedback(key, null);
  } else {
    like.classList.add('active');
    dislike.classList.remove('active');
    _sendFeedback(key, 'like');
  }
}

function _fbDislike(btn) {
  const bar = btn.closest('.msg-actions');
  const key = bar.dataset.key;
  const like = bar.querySelector('.msg-like');
  const dislike = bar.querySelector('.msg-dislike');
  like.classList.remove('active');
  if (dislike.classList.contains('active')) {
    dislike.classList.remove('active');
    _closeReasons(bar);
    _sendFeedback(key, null);
  } else {
    dislike.classList.add('active');
    _sendFeedback(key, 'dislike');     // dislike ghi nhận ngay, lý do tùy chọn
    _openReasons(bar, key);
  }
}

function _closeReasons(bar) {
  const next = bar.nextElementSibling;
  if (next && next.classList.contains('fb-reasons')) next.remove();
}

function _openReasons(bar, key) {
  _closeReasons(bar);
  const panel = document.createElement('div');
  panel.className = 'fb-reasons';
  panel.dataset.key = key;
  panel.innerHTML =
    `<span class="fb-label">Vì sao chưa tốt?</span>` +
    FB_REASONS.map(r => `<button class="fb-chip" onclick="_pickReason(this,'${r.code}')">${r.label}</button>`).join('') +
    `<button class="fb-chip fb-other" onclick="_otherReason(this)">Khác</button>`;
  bar.insertAdjacentElement('afterend', panel);
}

function _pickReason(chip, code) {
  const panel = chip.closest('.fb-reasons');
  panel.querySelectorAll('.fb-chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');
  const input = panel.querySelector('.fb-other-input');
  if (input) input.remove();
  _sendFeedback(panel.dataset.key, 'dislike', code);
}

function _otherReason(chip) {
  const panel = chip.closest('.fb-reasons');
  panel.querySelectorAll('.fb-chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');
  if (panel.querySelector('.fb-other-input')) return;
  const wrap = document.createElement('div');
  wrap.className = 'fb-other-input';
  wrap.innerHTML = `<input type="text" placeholder="Nhập góp ý..." /><button>Gửi</button>`;
  panel.appendChild(wrap);
  const input = wrap.querySelector('input');
  const sendBtn = wrap.querySelector('button');
  input.focus();
  const send = () => {
    _sendFeedback(panel.dataset.key, 'dislike', 'other', input.value.trim());
    sendBtn.textContent = 'Đã gửi';
  };
  sendBtn.onclick = send;
  input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
}

function _renderMessage(role, html, alreadyParsed = false) {
  const div = document.createElement('div');
  div.className = `message ${role}-message`;
  const avatarBot = `<div class="msg-avatar bot-avatar"><img src="../assets/images/robot.png" alt="Bot" /></div>`;
  const avatarUser = `<div class="msg-avatar user-avatar"><img src="../assets/images/question.png" alt="User" /></div>`;
  const content = role === 'bot'
    ? (alreadyParsed ? html : parseMarkdown(html))
    : html.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  if (role === 'user') {
    div.innerHTML = `<div class="message-bubble">${content}</div>${avatarUser}`;
  } else {
    const key = _nextMsgKey();
    div.innerHTML = `${avatarBot}<div class="msg-col"><div class="message-bubble">${content}</div>${_botActions(key)}</div>`;
  }
  messagesContainer.appendChild(div);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

let thinkingCounter = 0;
function appendThinking() {
  const id = 'thinking-' + (++thinkingCounter);
  const div = document.createElement('div');
  div.className = 'message bot-message';
  div.id = id;
  const avatarBot = `<div class="msg-avatar bot-avatar"><img src="../assets/images/robot.png" alt="Bot" /></div>`;
  div.innerHTML = `${avatarBot}<div class="message-bubble thinking-bubble">
    <div class="thinking-steps" id="steps-${id}"></div>
  </div>`;
  messagesContainer.appendChild(div);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  return id;
}

function addStepToThinking(thinkingId, label) {
  const el = document.getElementById('steps-' + thinkingId);
  if (!el) return;
  el.innerHTML = '';
  const step = document.createElement('div');
  step.className = 'thinking-step';
  step.innerHTML = `<span class="thinking-step-dot"></span><span class="thinking-step-label">${label}</span>`;
  el.appendChild(step);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function removeThinking(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

let chartCounter = 0;
function appendChart(data, skipSave = false) {
  if (!skipSave) {
    const s = sessions.find(x => x.id === activeId);
    if (s) s.messages.push({ role: 'chart', data });
  }
  _renderChart(data);
}

function _renderChart(data) {
  const chartId = 'chart-' + (++chartCounter);
  const avatarBot = `<div class="msg-avatar bot-avatar"><img src="../assets/images/robot.png" alt="Bot" /></div>`;
  const div = document.createElement('div');
  div.className = 'message bot-message chart-message';
  const cols = data.columns || [];
  const rows = (data.data || []).map(r => {
    const v = r[0];
    const missing = v === null || v === undefined || String(v).trim() === '' || String(v).trim().toUpperCase() === 'NAN';
    return missing ? ['Không có dữ liệu', ...r.slice(1)] : r;
  });
  const ctype = data.chart_type || 'bar';

  const n = rows.length;
  let chartH, marginL, marginB;
  if (ctype === 'horizontal_bar') {
    chartH = Math.max(320, n * 28 + 80);
    marginL = 130;
    marginB = 60;
  } else if (ctype === 'pie') {
    chartH = 360;
    marginL = 40; marginB = 40;
  } else if (ctype === 'bar') {
    chartH = 340;
    marginL = 60;
    marginB = n > 8 ? 100 : 70;
  } else {
    chartH = 320;
    marginL = 60; marginB = 60;
  }

  const downloadBtn = `<button class="msg-action" title="Tải ảnh" onclick="Plotly.downloadImage('${chartId}', {format:'png', width:900, height:500, filename:'bieu_do'})">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  </button>`;
  const key = _nextMsgKey();
  const chartActions = _actionBar(key, downloadBtn);
  const insight = data.tong_quan ? `<div class="chart-insight">${data.tong_quan}</div>` : '';
  div.innerHTML = `${avatarBot}<div class="msg-col chart-col"><div class="message-bubble chart-bubble"><div id="${chartId}" style="width:100%;height:${chartH}px;"></div>${insight}</div>${chartActions}</div>`;
  messagesContainer.appendChild(div);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  const isHBar = ctype === 'horizontal_bar';
  const xTitle = isHBar ? (data.y_label || '') : (data.x_label || cols[0] || '');
  const yTitle = isHBar ? (data.x_label || '') : (data.y_label || '');

  const layout = {
    title: { text: data.title || '', font: { color: '#c8d8f0', size: 13 } },
    paper_bgcolor: '#030d22',
    plot_bgcolor: '#030d22',
    font: { color: '#7a90b8', size: 11 },
    xaxis: {
      title: { text: xTitle, standoff: 20 },
      gridcolor: 'rgba(79,142,247,0.1)', color: '#7a90b8', automargin: true,
      tickangle: (ctype === 'bar' && n > 8) ? -40 : 0,
      zerolinecolor: 'rgba(79,142,247,0.15)',
    },
    yaxis: {
      title: { text: yTitle, standoff: 8 },
      gridcolor: 'rgba(79,142,247,0.1)', color: '#7a90b8', automargin: true,
      tickfont: { size: 11 },
      zerolinecolor: 'rgba(79,142,247,0.15)',
    },
    margin: { l: marginL, r: 24, t: data.title ? 44 : 20, b: marginB },
    legend: { font: { color: '#c8d8f0' } },
  };

  let traces;
  if (ctype === 'pie') {
    traces = [{ type: 'pie', labels: rows.map(r => r[0]), values: rows.map(r => r[1]),
      textinfo: 'percent+label', marker: { line: { color: '#21262d', width: 1 } } }];
  } else if (ctype === 'scatter') {
    traces = cols.slice(1).map((name, i) => ({
      type: 'scatter', mode: 'markers', name,
      x: rows.map(r => r[0]), y: rows.map(r => r[i + 1]),
    }));
  } else if (ctype === 'line') {
    traces = cols.slice(1).map((name, i) => ({
      type: 'scatter', mode: 'lines+markers', name,
      x: rows.map(r => r[0]), y: rows.map(r => r[i + 1]),
    }));
  } else if (ctype === 'horizontal_bar') {
    traces = cols.slice(1).map((name, i) => ({
      type: 'bar', orientation: 'h', name,
      y: rows.map(r => r[0]), x: rows.map(r => r[i + 1]),
    }));
  } else {
    // bar / histogram / stacked_bar
    traces = cols.slice(1).map((name, i) => ({
      type: 'bar', name,
      x: rows.map(r => r[0]), y: rows.map(r => r[i + 1]),
    }));
    if (ctype === 'stacked_bar') {
      layout.barmode = 'stack';
    }
  }

  Plotly.newPlot(chartId, traces, layout, { responsive: true, displayModeBar: false });
}

// New chat button
document.getElementById('newChatBtn').addEventListener('click', () => {
  activeId = null;
  messagesContainer.innerHTML = '';
  chatArea.classList.add('welcome-mode');
  renderHistoryList();
});

// Search history
const searchBox = document.getElementById('searchBox');
const searchInput = document.getElementById('searchInput');
let searchQuery = '';

document.getElementById('searchBtn').addEventListener('click', () => {
  searchBox.hidden = !searchBox.hidden;
  if (!searchBox.hidden) searchInput.focus();
  else { searchQuery = ''; searchInput.value = ''; renderHistoryList(); }
});

searchInput.addEventListener('input', (e) => {
  searchQuery = e.target.value.trim().toLowerCase();
  renderHistoryList();
});

// Trả về text thuần của 1 message (HTML hoặc data chart)
function messageText(m) {
  if (m.role === 'chart') {
    const d = m.data || {};
    const cols = (d.columns || []).join(' ');
    const rows = (d.data || []).flat().join(' ');
    return `${d.title || ''} ${cols} ${rows}`;
  }
  const div = document.createElement('div');
  div.innerHTML = m.html || '';
  return div.textContent || '';
}

function sessionMatches(s, q) {
  if (s.title.toLowerCase().includes(q)) return true;
  return (s.messages || []).some(m => messageText(m).toLowerCase().includes(q));
}

// Override renderHistoryList: lọc theo title + nội dung tất cả message
const _origRenderHistoryList = renderHistoryList;
renderHistoryList = function() {
  if (!searchQuery) return _origRenderHistoryList();
  const all = sessions;
  sessions = all.filter(s => sessionMatches(s, searchQuery));
  _origRenderHistoryList();
  sessions = all;
};

// Suggestion cards (welcome mode)
document.querySelectorAll('.suggestion-card').forEach(btn => {
  btn.addEventListener('click', () => {
    const q = btn.dataset.q || btn.textContent.trim();
    chatInput.value = q;
    chatInput.dispatchEvent(new Event('input'));
    sendMessage();
  });
});

// Load lịch sử từ backend lúc khởi động
loadSessionsFromBackend();
