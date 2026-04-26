"""
src/littrans/ui/epub_ui.py — EPUB Processor UI tab.

[BUG FIX] _launch worker: removed duplicate __DONE__ signal.
  process_all_epubs() already puts __DONE__ via log_queue param.
  Worker was putting a second __DONE__ causing UI to stop draining
  the queue prematurely.
"""
from __future__ import annotations

import queue
import time
import threading
from pathlib import Path
from typing import Any


def _get_settings():
    from littrans.config.settings import settings
    return settings


def render_epub_tab(S: Any) -> None:
    import streamlit as st

    st.subheader("📚 EPUB Processor")
    st.caption(
        "Chuyển đổi file `.epub` thành các chương trong `inputs/{tên_epub}/` "
        "sẵn sàng cho pipeline dịch."
    )

    # ep_* job state initialized via init_all_jobs(app.py)

    # Kiểm tra deps
    try:
        import ebooklib
        from bs4 import BeautifulSoup
    except ImportError:
        st.error(
            "❌ Thiếu thư viện xử lý EPUB.\n\n"
            "Chạy lệnh sau để cài đặt:\n"
            "```bash\npip install ebooklib beautifulsoup4\n```"
        )
        return

    settings = _get_settings()
    t_upload, t_queue, t_result = st.tabs(["📤 Upload & Xử lý", "📋 Hàng chờ", "✅ Kết quả"])

    with t_upload:
        _tab_upload(S, settings)
    with t_queue:
        _tab_queue(S, settings)
    with t_result:
        _tab_result(S, settings)


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — UPLOAD & XỬ LÝ
# ═══════════════════════════════════════════════════════════════════

def _tab_upload(S: Any, settings) -> None:
    import streamlit as st

    st.markdown(
        "**Bước 1:** Upload file `.epub` hoặc đặt file vào thư mục `epub/`.\n\n"
        "**Bước 2:** Nhấn **▶ Bắt đầu xử lý** — AI sẽ tự động bóc tách thành từng chương.\n\n"
        "**Bước 3:** Sang tab **📄 Dịch** để dịch như thường."
    )

    with st.expander("📤 Upload file .epub", expanded=True):
        uploaded = st.file_uploader(
            "Chọn file .epub",
            type=["epub"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded:
            settings.epub_dir.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                (settings.epub_dir / f.name).write_bytes(f.getvalue())
            st.success(f"✅ Đã lưu {len(uploaded)} file vào `{settings.epub_dir}/`")

    st.divider()
    output_mode = st.radio(
        "Output format",
        ["per_chapter", "merged"],
        format_func=lambda x: "📄 Per-chapter .md (mặc định — cho Dịch)" if x == "per_chapter"
                               else "📋 Merged .md (1 file gộp toàn sách)",
        horizontal=True,
        key="epub_output_mode",
    )
    if output_mode == "per_chapter":
        st.caption("Sau khi xử lý xong, các chương sẽ nằm tại:")
        st.code("inputs/{tên_epub}/0001_Chapter_Title.md\ninputs/{tên_epub}/0002_Chapter_Title.md\n...")
    else:
        st.caption("Sau khi xử lý xong, file gộp sẽ nằm tại:")
        st.code("epub_merged/{tên_epub}.md")

    epub_files = sorted(settings.epub_dir.glob("*.epub")) if settings.epub_dir.exists() else []

    if not epub_files:
        st.info(
            f"Chưa có file `.epub` nào trong `{settings.epub_dir}/`. "
            "Upload file ở trên để bắt đầu."
        )
        return

    st.markdown(f"**{len(epub_files)} file sẵn sàng xử lý:**")
    for ep in epub_files[:10]:
        st.caption(f"  📖 {ep.name}  ({ep.stat().st_size/1_048_576:.1f} MB)")
    if len(epub_files) > 10:
        st.caption(f"  ... và {len(epub_files)-10} file khác")

    col_btn, col_info = st.columns([1, 3])

    ep_alive = S.ep_running and S.ep_thread is not None and \
               getattr(S.ep_thread, "is_alive", lambda: False)()

    if not ep_alive:
        if col_btn.button("▶ Bắt đầu xử lý", type="primary"):
            from littrans.ui.core.state import reset_job
            reset_job(S, "ep")
            S.ep_logs = []
            S.ep_q    = queue.Queue()
            S.ep_thread = _launch(S.ep_q, output_mode=S.get("epub_output_mode", "per_chapter"))
            S.ep_running  = True
            S.ep_last_log = time.time()
            st.rerun()
    else:
        col_btn.button("⏳ Đang xử lý…", disabled=True)
        col_info.warning("🔄 Đang xử lý — có thể mất vài phút. (Có thể chuyển tab khác)")

    if S.ep_running or S.ep_logs:
        _handle_log(S)


def _launch(log_queue: queue.Queue, output_mode: str = "per_chapter"):
    """
    Launch epub processor in background thread.

    BUG FIX: Removed duplicate __DONE__ signal.
    process_all_epubs() already calls log_queue.put("__DONE__") internally.
    The old code put a second __DONE__ here, causing _handle_log to stop
    reading the queue before all messages were drained.
    """
    def _worker():
        import io, sys, traceback

        class _Cap(io.TextIOBase):
            def write(self, t: str) -> int:
                s = t.rstrip()
                if s:
                    log_queue.put(s)
                elif "\n" in t:
                    log_queue.put("")
                return len(t)
            def flush(self): pass

        old = sys.stdout
        sys.stdout = _Cap()
        try:
            from littrans.tools.epub_processor import process_all_epubs
            # process_all_epubs already puts "__DONE__" via log_queue param
            process_all_epubs(log_queue=log_queue, output_mode=output_mode)
            # DO NOT put "__DONE__" again here — it's already done inside process_all_epubs
        except Exception as e:
            log_queue.put(f"❌ Lỗi: {e}")
            for ln in traceback.format_exc().splitlines()[-8:]:
                if ln.strip():
                    log_queue.put(f"   {ln}")
            # Only put __DONE__ on exception since process_all_epubs didn't finish
            log_queue.put("__DONE__")
        finally:
            sys.stdout = old

    th = threading.Thread(target=_worker, daemon=True)
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        add_script_run_ctx(th)
    except ImportError:
        pass
    th.start()
    return th


def _handle_log(S: Any) -> None:
    """Render only — drain handled by app.py poll_all."""
    import streamlit as st
    if S.ep_logs:
        with st.expander("📋 Nhật ký xử lý", expanded=bool(S.ep_running)):
            st.code("\n".join(S.ep_logs[-300:]), language=None)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — HÀNG CHỜ
# ═══════════════════════════════════════════════════════════════════

def _tab_queue(S: Any, settings) -> None:
    import streamlit as st

    col1, col2 = st.columns([4, 1])
    col1.markdown(f"#### 📋 File đang chờ xử lý (`{settings.epub_dir}/`)")
    if col2.button("↺ Làm mới", key="epub_q_refresh"):
        st.rerun()

    if not settings.epub_dir.exists():
        st.info("Thư mục `epub/` chưa tồn tại.")
        return

    files = sorted(settings.epub_dir.glob("*.epub"))
    if not files:
        st.info("Không có file `.epub` nào đang chờ.")
        return

    for ep in files:
        c1, c2, c3 = st.columns([4, 1, 1])
        c1.write(f"📖 {ep.name}")
        c2.caption(f"{ep.stat().st_size/1_048_576:.1f} MB")
        if c3.button("🗑 Xóa", key=f"del_epub_{ep.name}"):
            ep.unlink()
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — KẾT QUẢ
# ═══════════════════════════════════════════════════════════════════

def _tab_result(S: Any, settings) -> None:
    import streamlit as st

    col1, col2 = st.columns([4, 1])
    col1.markdown("#### ✅ Chapters đã được tạo trong `inputs/`")
    if col2.button("↺ Làm mới", key="epub_r_refresh"):
        st.rerun()

    input_dir = settings.input_dir
    if not input_dir.exists():
        st.info("Thư mục `inputs/` chưa có dữ liệu.")
        return

    book_dirs = sorted([d for d in input_dir.iterdir() if d.is_dir()])

    if not book_dirs:
        st.info(
            "Chưa có sách nào được xử lý. "
            "Upload file `.epub` ở tab **📤 Upload & Xử lý** và nhấn **Bắt đầu xử lý**."
        )
        return

    for book_dir in book_dirs:
        chapters = sorted([*book_dir.glob("*.txt"), *book_dir.glob("*.md")])
        if not chapters:
            continue

        with st.expander(f"📚 **{book_dir.name}**  —  {len(chapters)} chương", expanded=False):
            st.success(f"Sẵn sàng dịch! Sang tab **📄 Dịch** và chọn truyện `{book_dir.name}`.")
            st.code(
                f"# Hoặc dùng CLI:\npython scripts/main.py translate --book {book_dir.name}",
                language="bash",
            )
            st.caption(f"📁 `inputs/{book_dir.name}/`")

            for ch in chapters[:3]:
                preview = ch.read_text(encoding='utf-8', errors='replace')[:120]
                st.caption(f"`{ch.name}`  →  {preview[:80]}…")
            if len(chapters) > 3:
                st.caption(f"... và {len(chapters)-3} chương khác")

            if st.button(
                f"🗑 Xóa tất cả chapters của '{book_dir.name}'",
                key=f"del_book_{book_dir.name}",
            ):
                import shutil
                shutil.rmtree(book_dir)
                st.rerun()