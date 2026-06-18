// Base URL của API — DÙNG CHUNG cho mọi trang.
// Đổi domain production chỉ cần sửa Ở ĐÂY (trước đây lặp ở 4 file JS).
// Lưu ý: file này phải được nạp TRƯỚC các script khác trong mỗi HTML.
const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://localhost:8000'
  : 'https://kltn-chatbot-vpqm.onrender.com';
