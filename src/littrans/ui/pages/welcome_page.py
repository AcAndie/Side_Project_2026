"""src/littrans/ui/pages/welcome_page.py — Welcome / first-setup screen."""
from __future__ import annotations

import time

import streamlit as st

from littrans.ui.env_utils import _save_env


def render_welcome() -> None:
    st.markdown("""
    <div class="welcome-card">
        <h2 style="margin:0 0 8px 0">👋 Chào mừng đến với LiTTrans!</h2>
        <p style="color:#555;margin:0;font-size:15px">
            Dịch truyện LitRPG / Tu Tiên tự động từ tiếng Anh sang tiếng Việt.<br>
            Nhất quán tên nhân vật, xưng hô và kỹ năng từ đầu đến cuối.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Bắt đầu trong 3 bước")
    c1, c2, c3 = st.columns(3)
    _steps = [
        (c1, "1", "🔑 Lấy API Key",
         "Truy cập <b>aistudio.google.com</b>, đăng nhập Google → "
         "<b>Get API key → Create API key</b>.<br><br>Miễn phí, không cần thẻ tín dụng."),
        (c2, "2", "⚙️ Nhập API Key bên dưới",
         "Dán key vào ô bên dưới và nhấn <b>Lưu & bắt đầu</b>.<br><br>"
         "Key có dạng <code>AIzaSy...</code>"),
        (c3, "3", "📄 Upload chương và dịch",
         "Vào tab <b>📄 Dịch</b>, upload file <code>.txt</code>/<code>.md</code>, "
         "nhấn <b>▶ Dịch</b>."),
    ]
    for col, num, title, body in _steps:
        with col:
            st.markdown(f"""<div class="step-card">
                <div class="step-num">{num}</div>
                <h4>{title}</h4>
                <p style="color:#555;font-size:13px">{body}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Nhập Gemini API Key")
    st.markdown("[Lấy miễn phí tại aistudio.google.com →](https://aistudio.google.com)")

    col_key, col_btn = st.columns([4, 1])
    api_key = col_key.text_input("API Key", type="password",
                                  placeholder="AIzaSy...", label_visibility="collapsed")
    if col_btn.button("💾 Lưu & bắt đầu", type="primary", use_container_width=True):
        if not api_key.strip():
            st.error("Vui lòng nhập API Key.")
        elif not api_key.strip().startswith("AIza"):
            st.warning("⚠️  Key thường bắt đầu bằng 'AIza...' — kiểm tra lại.")
        else:
            try:
                _save_env({"GEMINI_API_KEY": api_key.strip()})
                st.success("✅ Đã lưu! Đang tải lại...")
                time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"Không thể lưu: {e}")

    with st.expander("💡 Câu hỏi thường gặp"):
        st.markdown("""
**Miễn phí không?** Gói miễn phí đủ dịch 30–50 chương/ngày. Không cần thẻ tín dụng.

**Dữ liệu an toàn không?** API Key lưu trong file `.env` trên máy bạn, không chia sẻ với ai.

**Cần biết lập trình không?** Không. Giao diện web, thao tác bằng nút bấm.

**Hỗ trợ file nào?** `.txt` và `.md`. File `.epub` → dùng tab **📚 EPUB** để chuyển trước.
        """)
