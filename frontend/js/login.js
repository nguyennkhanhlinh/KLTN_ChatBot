const API = 'http://localhost:8000';

const form      = document.getElementById('loginForm');
const errorEl   = document.getElementById('loginError');
const loginBtn  = document.getElementById('loginBtn');
const pwToggle  = document.getElementById('pwToggle');
const pwInput   = document.getElementById('password');

pwToggle.addEventListener('click', () => {
  const show = pwInput.type === 'password';
  pwInput.type = show ? 'text' : 'password';
  pwToggle.querySelector('svg').style.opacity = show ? '1' : '0.4';
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('username').value.trim();
  const password = pwInput.value;

  if (!username || !password) {
    showError('Vui lòng nhập đầy đủ thông tin.');
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = 'Đang đăng nhập...';
  errorEl.hidden = true;

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.detail || 'Đăng nhập thất bại.');
      return;
    }
    localStorage.setItem('chatbot:token', data.access_token);
    localStorage.setItem('chatbot:username', data.username);
    localStorage.setItem('chatbot:role', data.role);
    window.location.replace('index.html');
  } catch {
    showError('Không kết nối được server. Hãy thử lại.');
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'Đăng nhập';
  }
});

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.hidden = false;
}
