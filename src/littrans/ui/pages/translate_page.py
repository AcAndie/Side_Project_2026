"""src/littrans/ui/pages/translate_page.py — Dịch chương page."""
from __future__ import annotations

import io as _io
import queue
import time

import streamlit as st

from littrans.ui.loaders import load_chapters, load_stats
from littrans.ui.ui_utils import _poll, _show_log


def render_translate() -> None:
    S = st.session_state
    chapters = load_chapters(S.current_novel)
    done  = sum(1 for c in chapters if c["done"])
    total = len(chapters)

    st.subheader("📄 Dịch chương")

    with st.expander("📁 Upload file chương (.txt / .md)", expanded=not chapters):
        st.caption("Đặt tên theo thứ tự: `chapter_001.txt`, `chapter_002.txt`, ...")
        uploaded = st.file_uploader("Chọn file", type=["txt", "md"],
                                    accept_multiple_files=True, label_visibility="collapsed")
        if uploaded:
            try:
                from littrans.config.settings import settings as cfg
                inp = cfg.active_input_dir
            except Exception:
                from pathlib import Path
                _ROOT = Path(__file__).resolve().parents[4]
                novel = S.current_novel
                inp = _ROOT / "inputs" / novel if novel else _ROOT / "inputs"
            inp.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                (inp / f.name).write_bytes(f.getvalue())
            st.success(f"✅ Đã lưu {len(uploaded)} file vào `{inp}`")
            load_chapters.clear(); st.rerun()

    if not chapters:
        st.info("**Chưa có chương nào.** Upload file ở trên, hoặc dùng tab **📚 EPUB** "
                "để chuyển file epub trước.")
        return

    st.progress(done / total,
                text=f"Tiến độ: {done}/{total} chương ({int(done/total*100)}%)")

    col_f1, col_f2, _ = st.columns([1, 1, 3])
    show_filter = col_f1.selectbox("Hiển thị", ["Tất cả", "Chưa dịch", "Đã dịch"],
                                   label_visibility="collapsed")
    if col_f2.button("↺ Làm mới danh sách"):
        load_chapters.clear(); st.rerun()

    filtered = chapters
    if show_filter == "Chưa dịch": filtered = [c for c in chapters if not c["done"]]
    elif show_filter == "Đã dịch":  filtered = [c for c in chapters if c["done"]]

    if filtered:
        h0, h1, h2, h3 = st.columns([0.4, 3, 0.8, 1.5])
        h0.caption("STT"); h1.caption("File")
        h2.caption("Kích thước"); h3.caption("Trạng thái")
        for ch in filtered:
            c0, c1, c2, c3 = st.columns([0.4, 3, 0.8, 1.5])
            c0.write(f"`{ch['idx']+1:03d}`")
            c1.write(ch["name"])
            c2.write(ch["size"])
            badge = "badge-ok" if ch["done"] else "badge-warn"
            label = "✅ Đã dịch" if ch["done"] else "⬜ Chưa dịch"
            c3.markdown(f'<span class="badge {badge}">{label}</span>', unsafe_allow_html=True)
    elif show_filter != "Tất cả":
        st.info(f"Không có chương nào ở trạng thái '{show_filter}'.")

    st.divider()

    pending = total - done
    col_btn, col_info = st.columns([1, 4])
    if not S.running:
        lbl = f"▶ Dịch {pending} chương" if pending > 0 else "▶ Dịch"
        if col_btn.button(lbl, type="primary", disabled=(not chapters or pending == 0)):
            S.logs = []; S.log_q = queue.Queue()
            from littrans.ui.runner import run_background
            S.run_thread = run_background(S.log_q, mode="run", novel_name=S.current_novel)
            S.running = True; st.rerun()
        if total and done == total:
            col_info.success("🎉 Tất cả chương đã được dịch xong!")
        elif total and pending > 0:
            col_info.info(f"💡 Còn {pending} chương chưa dịch. Nhấn nút để bắt đầu.")
    else:
        col_btn.button("⏹ Đang chạy…", disabled=True)
        col_info.warning("🔄 Pipeline đang chạy — đừng đóng cửa sổ.")

    if S.running or S.logs:
        if S.running:
            if _poll("log_q", "logs", "run_thread"):
                S.running = False
                S.logs.extend(["─" * 56, "✅ Pipeline hoàn tất."])
                load_chapters.clear(); load_stats.clear()
        with st.expander("📋 Nhật ký xử lý", expanded=S.running):
            _show_log(S.logs)
        if S.running:
            time.sleep(0.9); st.rerun()

    # ── EPUB Export ───────────────────────────────────────────────
    translated = [c for c in chapters if c["done"]]
    if translated and not S.running:
        st.divider()
        with st.expander("📖 Xuất EPUB", expanded=False):
            st.caption(f"{len(translated)} chương đã dịch sẵn sàng xuất EPUB.")
            c1, c2 = st.columns(2)
            epub_title  = c1.text_input(
                "Tiêu đề", key="epub_exp_title",
                value=S.current_novel.replace("_", " ").title() if S.current_novel else "",
            )
            epub_author = c2.text_input("Tác giả", value="Unknown", key="epub_exp_author")

            if st.button("🔄 Tạo EPUB", key="epub_gen_btn"):
                try:
                    from littrans.tools.epub_exporter import (
                        export_to_epub, EpubExportMeta, get_translated_chapters,
                    )
                    chaps = get_translated_chapters(S.current_novel)
                    if not chaps:
                        st.error("Không tìm thấy file *_VN.txt trong outputs/")
                    else:
                        buf = _io.BytesIO()
                        export_to_epub(
                            chaps, buf,
                            EpubExportMeta(
                                title=epub_title or S.current_novel,
                                author=epub_author or "Unknown",
                            ),
                        )
                        S["epub_export_bytes"] = buf.getvalue()
                        S["epub_export_novel"] = S.current_novel
                        st.success(f"✅ EPUB từ {len(chaps)} chương. Nhấn Download bên dưới.")
                except Exception as _exc:
                    st.error(f"❌ Lỗi xuất EPUB: {_exc}")

            if S.get("epub_export_bytes") and S.get("epub_export_novel") == S.current_novel:
                fname = f"{S.current_novel or 'novel'}.epub"
                st.download_button(
                    "⬇️ Download EPUB",
                    data=S["epub_export_bytes"],
                    file_name=fname,
                    mime="application/epub+zip",
                    key="epub_dl_btn",
                )
