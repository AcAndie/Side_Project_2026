"""src/littrans/ui/pages/chapters_page.py — Xem chương page."""
from __future__ import annotations

import html as _html
import queue
import time

import streamlit as st

from littrans.ui.loaders import load_chapters, load_chapter_content, load_stats
from littrans.ui.ui_utils import _poll, _show_log, split_view, diff_view


def render_chapters() -> None:
    S = st.session_state
    chapters = load_chapters(S.current_novel)
    if not chapters:
        st.info("**Chưa có chương nào.** Vào tab **📄 Dịch** để upload và dịch.")
        return

    col_list, col_view = st.columns([1, 3.2])
    with col_list:
        search = st.text_input("🔍", placeholder="Tìm chương…",
                               label_visibility="collapsed", key="ch_s")
        filtered = [c for c in chapters
                    if not search or search.lower() in c["name"].lower()]
        st.caption(f"{len(filtered)} / {len(chapters)} chương")
        for ch in filtered:
            icon   = "✅" if ch["done"] else "⬜"
            is_sel = ch["idx"] == S.sel_ch
            if st.button(f"{icon} {ch['name']}", key=f"chbtn_{ch['idx']}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                S.sel_ch = ch["idx"]; S.show_rt = False; S.rt_logs = []; st.rerun()

    with col_view:
        idx = min(S.sel_ch, len(chapters) - 1)
        _render_chapter_detail(chapters[idx])


def _render_chapter_detail(ch: dict) -> None:
    S = st.session_state
    content = load_chapter_content(str(ch["path"]), str(ch["vn_path"]), ch["done"])
    raw, vn = content["raw"], content["vn"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("File", ch["name"])
    m2.metric("Kích thước", ch["size"])
    m3.metric("Bản dịch", "✅ Có" if ch["done"] else "❌ Chưa")

    nl_violations: list[str] = []
    if ch["done"] and vn:
        try:
            from littrans.context.name_lock import build_name_lock_table, validate_translation
            nl_violations = validate_translation(vn, build_name_lock_table())
        except Exception:
            pass
    m4.metric("Name Lock", f"⚠️ {len(nl_violations)} vi phạm" if nl_violations else "✅ Ổn",
              help="Số lần tên nhân vật bị dịch không đúng theo bảng đã chốt")

    if nl_violations:
        with st.expander(f"🔒 {len(nl_violations)} vi phạm Name Lock", expanded=False):
            for w in nl_violations:
                st.markdown(f'<span class="badge badge-warn">{_html.escape(w.strip())}</span>',
                            unsafe_allow_html=True)
            st.caption("Để sửa hàng loạt: `python scripts/main.py fix-names`")

    view_tabs = st.tabs(["🔀 Song song", "📄 Bản gốc", "🇻🇳 Bản dịch", "⚡ So sánh"])

    with view_tabs[0]:
        if not ch["done"]:
            st.info("Chưa có bản dịch.")
            if raw: st.text_area(" ", raw, height=420, disabled=True, label_visibility="collapsed")
        elif not raw: st.warning("Không đọc được file gốc.")
        else:         split_view(raw, vn)

    with view_tabs[1]:
        if raw: st.text_area(" ", raw, height=500, disabled=True, label_visibility="collapsed")
        else:   st.info("Không đọc được file gốc.")

    with view_tabs[2]:
        if ch["done"] and vn:
            st.text_area(" ", vn, height=500, disabled=True, label_visibility="collapsed")
            _, c2 = st.columns([1, 5])
            c2.download_button("⬇ Tải xuống bản dịch",
                               data=vn.encode("utf-8"),
                               file_name=f"{ch['path'].stem}_VN.txt",
                               mime="text/plain", key="dl_vn")
        elif not ch["done"]: st.info("Chưa có bản dịch.")
        else:                st.warning("Không đọc được file dịch.")

    with view_tabs[3]:
        if not ch["done"]:      st.info("Cần có bản dịch để so sánh.")
        elif not raw or not vn: st.warning("Thiếu nội dung.")
        else:
            st.caption("🟢 Đoạn thêm  🟡 Đoạn thay đổi  🔴 Đoạn bị xóa")
            diff_view(raw, vn)

    st.divider()
    rt_col, _ = st.columns([1, 5])
    if rt_col.button("✕ Đóng" if S.show_rt else "↺ Dịch lại chương này",
                     key="rt_toggle", type="secondary"):
        S.show_rt = not S.show_rt; S.rt_logs = []; st.rerun()

    if S.show_rt:
        with st.container(border=True):
            st.markdown(f"**↺ Dịch lại — `{ch['name']}`**")
            if ch["done"]:
                st.warning("⚠️  Bản dịch hiện tại sẽ bị **ghi đè**.")

            update_data = False
            force_scout = False
            with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
                c1, c2 = st.columns(2)
                update_data = c1.checkbox("Cập nhật nhân vật/từ điển sau khi dịch",
                    help="Tự động cập nhật data nhân vật và thuật ngữ mới.")
                force_scout = c2.checkbox("Chạy Scout AI trước",
                    help="Scout đọc chương gần đây để cập nhật ngữ cảnh.")

            if not S.rt_running:
                if st.button("⚡ Xác nhận dịch lại", type="primary", key="rt_confirm"):
                    S.rt_logs = []; S.rt_q = queue.Queue()
                    from littrans.ui.runner import run_background
                    S.rt_thread = run_background(
                        S.rt_q, mode="retranslate", novel_name=S.current_novel,
                        filename=ch["name"], update_data=update_data,
                        force_scout=force_scout,
                        all_files=[c["name"] for c in load_chapters(S.current_novel)],
                        chapter_index=ch["idx"],
                    )
                    S.rt_running = True; st.rerun()
            else:
                st.info("⏳ Đang dịch lại…")

            if S.rt_running or S.rt_logs:
                if S.rt_running:
                    if _poll("rt_q", "rt_logs", "rt_thread"):
                        S.rt_running = False
                        S.rt_logs.extend(["─" * 56, "✅ Dịch lại hoàn tất."])
                        load_chapters.clear(); load_stats.clear()
                with st.expander("📋 Nhật ký", expanded=S.rt_running):
                    _show_log(S.rt_logs)
                if S.rt_running:
                    time.sleep(0.9); st.rerun()
