const BASE_URL = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://localhost:8000'
  : 'https://kltn-chatbot.onrender.com';

localStorage.removeItem("chatbot:token");
localStorage.removeItem("chatbot:username");
localStorage.removeItem("chatbot:role");

const form = document.getElementById("registerForm");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirmPassword");
const errorDiv = document.getElementById("registerError");
const btn = document.getElementById("registerBtn");

document.getElementById("pwToggle").addEventListener("click", () => {
  const isText = passwordInput.type === "text";
  passwordInput.type = isText ? "password" : "text";
});

function showError(msg) {
  errorDiv.textContent = msg;
  errorDiv.hidden = false;
}

function hideError() {
  errorDiv.hidden = true;
}

function showSuccess() {
  const toast = document.createElement("div");
  toast.className = "register-toast";
  toast.innerHTML = `
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
    Đăng ký thành công!
  `;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => window.location.href = "login.html", 2000);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const confirm = confirmInput.value;
  const email = document.getElementById("email").value.trim();
  const phone = document.getElementById("phone").value.trim();

  if (username.length < 3) return showError("Tên đăng nhập phải có ít nhất 3 ký tự.");
  if (password.length < 6) return showError("Mật khẩu phải có ít nhất 6 ký tự.");
  if (password !== confirm) return showError("Mật khẩu xác nhận không khớp.");
  if (!email) return showError("Vui lòng nhập Gmail.");
  if (!phone) return showError("Vui lòng nhập số điện thoại.");

  btn.disabled = true;
  btn.textContent = "Đang đăng ký...";

  // Timeout 30s — tránh nút kẹt vô hạn khi backend không phản hồi (chưa chạy / cold-start).
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, email, phone }),
      signal: controller.signal,
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Đăng ký thất bại.");

    showSuccess();
  } catch (err) {
    const msg = err.name === "AbortError"
      ? "Máy chủ phản hồi quá lâu. Vui lòng kiểm tra kết nối và thử lại."
      : (err.message === "Failed to fetch"
          ? "Không kết nối được máy chủ. Vui lòng thử lại sau."
          : err.message);
    showError(msg);
    btn.disabled = false;
    btn.innerHTML = `Đăng ký <svg viewBox="0 0 24 24" width="15" height="15"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`;
  } finally {
    clearTimeout(timer);
  }
});
