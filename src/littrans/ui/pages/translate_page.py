"""
src/littrans/ui/pages/translate_page.py — Tab Dịch (Phase 3 rebuild).

Merges legacy translate_page + chapters_page + pipeline_page *_translate
modes. Single full page:

  ┌──────── Top: progress + Run All / Stop / Upload ─────────┐
  │                                                          │
  │ Left list (chapters) │ Right reader (split / VN / diff)  │
  │                      │ + Retranslate / Delete            │
  │                                                          │
  └──────── Bottom: log expander (auto-expand on run) ───────┘

Run / retranslate / delete sửa thẳng inputs/{novel}/ + outputs/{novel}/.
"""
from __future__ import annotations

import html as _html
import os
import queue
import time
from pathlib import Path

import streamlit as st

from littrans.ui.loaders import (
    load_chapters, load_chapter_content, load_stats,
)
from littrans.ui.ui_utils import _show_log, split_view, diff_view


# ── Source-file ops ──────────────────────────────────────────────

def _delete_chapter(path: Path, vn_path: Path) -> tuple[bool, bool]:
    """Xóa chapter file gốc + bản dịch (nếu có). Trả về (raw_removed, vn_removed)."""
    raw_ok = vn_ok = False
    try:
        if path.exists():
            path.unlink()
            raw_ok = True
    except Exception:
        pass
    try:
        if vn_path.exists():
            vn_path.unlink()
            vn_ok = True
    except Exception:
        pass
    return raw_ok, vn_ok


# ── Main render ──────────────────────────────────────────────────

def render_translate() -> None:
    S = st.session_state
    chapters = load_chapters(S.current_novel)
    done  = sum(1 for c in chapters if c["done"])
    total = len(chapters)

    st.subheader("🇻🇳 Dịch")

    # ── Top control bar ──────────────────────────────────────────
    with st.expander("📁 Upload file chương (.txt / .md)", expanded=not chapters):
        st.caption("Đặt tên theo thứ tự: `chapter_001.txt`, `chapter_002.txt`, ...")
        uploaded = st.file_uploader(
            "Chọn file", type=["txt", "md"],
            accept_multiple_files=True, label_visibility="collapsed",
        )
        if uploaded:
            try:
                from littrans.config.settings import settings as cfg
                inp = cfg.active_input_dir
            except Exception:
                _ROOT = Path(__file__).resolve().parents[4]
                novel = S.current_novel
                inp = _ROOT / "inputs" / novel if novel else _ROOT / "inputs"
            inp.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                (inp / f.name).write_bytes(f.getvalue())
            st.success(f"✅ Đã lưu {len(uploaded)} file vào `{inp}`")
            load_chapters.clear(); st.rerun()

    if not chapters:
        st.info(
            "**Chưa có chương nào.** Upload file ở trên, hoặc dùng tab **🌐 Cào** "
            "để cào web → inputs, hoặc tab **📦 Export** để chuyển EPUB → chương."
        )
        return

    pct = done / total if total else 0.0
    st.progress(
        pct, text=f"Tiến độ: {done}/{total} chương ({int(pct*100)}%)"
    )

    pending = total - done
    col_btn, col_info = st.columns([1, 4])

    tx_alive = S.tx_running and S.tx_thread is not None and \
               getattr(S.tx_thread, "is_alive", lambda: False)()

    if not tx_alive:
        lbl = f"▶ Dịch {pending} chương" if pending > 0 else "▶ Dịch"
        if col_btn.button(lbl, type="primary", disabled=(pending == 0)):
            from littrans.ui.core.state import reset_job
            reset_job(S, "tx")
            S.tx_logs = []
            S.tx_q    = queue.Queue()
            from littrans.ui.runner import run_background
            S.tx_thread   = run_background(S.tx_q, mode="run", novel_name=S.current_novel)
            S.tx_running  = True
            S.tx_last_log = time.time()
            st.rerun()
        if total and done == total:
            col_info.success("🎉 Tất cả chương đã được dịch xong!")
        elif pending > 0:
            col_info.info(f"💡 Còn {pending} chương chưa dịch. Nhấn nút để bắt đầu.")
    else:
        col_btn.button("⏹ Đang chạy…", disabled=True)
        col_info.warning("🔄 Pipeline đang chạy — đừng đóng cửa sổ. (Có thể chuyển tab khác)")

    # Cache invalidation when tx finishes
    if (not S.tx_running) and S.tx_logs and not S.get("_tx_post_clear_done"):
        load_chapters.clear(); load_stats.clear()
        S["_tx_post_clear_done"] = True
    if S.tx_running:
        S["_tx_post_clear_done"] = False

    st.divider()

    # ── Reader (chapter list + content) ─────────────────────────
    col_list, col_view = st.columns([1, 3.2])
    with col_list:
        search = st.text_input(
            "🔍", placeholder="Tìm chương…",
            label_visibility="collapsed", key="tx_search",
        )
        show_filter = st.selectbox(
            "Lọc", ["Tất cả", "Chưa dịch", "Đã dịch"],
            label_visibility="collapsed", key="tx_filter",
        )
        filtered = [
            c for c in chapters
            if (not search or search.lower() in c["name"].lower())
            and (
                show_filter == "Tất cả"
                or (show_filter == "Chưa dịch" and not c["done"])
                or (show_filter == "Đã dịch" and c["done"])
            )
        ]
        st.caption(f"{len(filtered)} / {len(chapters)} chương")
        for ch in filtered:
            icon   = "✅" if ch["done"] else "⬜"
            is_sel = ch["idx"] == S.sel_ch
            if st.button(
                f"{icon} {ch['name']}",
                key=f"tx_chbtn_{ch['idx']}",
                use_container_width=True,
                type="primary" if is_sel else "secondary",
            ):
                S.sel_ch = ch["idx"]
                S.show_rt = False
                S.rt_logs = []
                st.rerun()

    with col_view:
        idx = min(S.sel_ch, len(chapters) - 1)
        _render_chapter_detail(chapters[idx])

    # ── Bottom log panel ─────────────────────────────────────────
    if S.tx_running or S.tx_logs:
        st.divider()
        with st.expander(
            "📋 Nhật ký dịch (full pipeline)",
            expanded=bool(S.tx_running),
        ):
            _show_log(S.tx_logs)


# ── Chapter detail (from old chapters_page) ──────────────────────

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
    m4.metric(
        "Name Lock",
        f"⚠️ {len(nl_violations)} vi phạm" if nl_violations else "✅ Ổn",
        help="Số lần tên nhân vật bị dịch không đúng theo bảng đã chốt",
    )

    if nl_violations:
        with st.expander(f"🔒 {len(nl_violations)} vi phạm Name Lock", expanded=False):
            for w in nl_violations:
                st.markdown(
                    f'<span class="badge badge-warn">{_html.escape(w.strip())}</span>',
                    unsafe_allow_html=True,
                )
            st.caption("Để sửa hàng loạt: `python scripts/main.py fix-names`")

    view_tabs = st.tabs(["🔀 Song song", "📄 Bản gốc", "🇻🇳 Bản dịch", "⚡ So sánh"])

    with view_tabs[0]:
        if not ch["done"]:
            st.info("Chưa có bản dịch.")
            if raw:
                st.text_area(
                    " ", raw, height=420, disabled=True, label_visibility="collapsed",
                )
        elif not raw:
            st.warning("Không đọc được file gốc.")
        else:
            split_view(raw, vn)

    with view_tabs[1]:
        if raw:
            st.text_area(" ", raw, height=500, disabled=True, label_visibility="collapsed")
        else:
            st.info("Không đọc được file gốc.")

    with view_tabs[2]:
        if ch["done"] and vn:
            paragraphs = "".join(
                f"<p>{_html.escape(p)}</p>" for p in vn.split("\n\n") if p.strip()
            )
            st.markdown(
                f"<div class='reader-container'><div class='reader-text'>{paragraphs}</div></div>",
                unsafe_allow_html=True,
            )
            with st.expander("📝 Xem/copy text thô"):
                st.text_area(
                    " ", vn, height=400, disabled=True, label_visibility="collapsed",
                )
            _, c2 = st.columns([1, 5])
            c2.download_button(
                "⬇ Tải xuống bản dịch",
                data=vn.encode("utf-8"),
                file_name=f"{ch['path'].stem}_VN.txt",
                mime="text/plain",
                key=f"tx_dl_vn_{ch['idx']}",
            )
        elif not ch["done"]:
            st.info("Chưa có bản dịch.")
        else:
            st.warning("Không đọc được file dịch.")

    with view_tabs[3]:
        if not ch["done"]:
            st.info("Cần có bản dịch để so sánh.")
        elif not raw or not vn:
            st.warning("Thiếu nội dung.")
        else:
            st.caption("🟢 Đoạn thêm  🟡 Đoạn thay đổi  🔴 Đoạn bị xóa")
            diff_view(raw, vn)

    st.divider()
    rt_col, del_col, _ = st.columns([1, 1, 4])

    if rt_col.button(
        "✕ Đóng" if S.show_rt else "↺ Dịch lại chương này",
        key="tx_rt_toggle", type="secondary",
    ):
        S.show_rt = not S.show_rt
        S.rt_logs = []
        st.rerun()

    # Chapter delete (with confirm flag)
    confirm_key = f"_tx_del_confirm_{ch['idx']}"
    if not S.get(confirm_key):
        if del_col.button("🗑 Xóa chương", key=f"tx_del_btn_{ch['idx']}", help="Xóa file gốc + bản dịch"):
            S[confirm_key] = True
            st.rerun()
    else:
        if del_col.button("⚠️ Xác nhận xóa", key=f"tx_del_confirm_{ch['idx']}", type="primary"):
            raw_ok, vn_ok = _delete_chapter(ch["path"], ch["vn_path"])
            S[confirm_key] = False
            load_chapters.clear()
            load_stats.clear()
            msgs = []
            if raw_ok: msgs.append("file gốc")
            if vn_ok:  msgs.append("bản dịch")
            if msgs:
                st.success(f"✅ Đã xóa {' + '.join(msgs)}.")
            else:
                st.warning("Không có gì để xóa.")
            S.sel_ch = max(0, S.sel_ch - 1)
            st.rerun()
        if del_col.button("Hủy", key=f"tx_del_cancel_{ch['idx']}"):
            S[confirm_key] = False
            st.rerun()

    if S.show_rt:
        with st.container(border=True):
            st.markdown(f"**↺ Dịch lại — `{ch['name']}`**")
            if ch["done"]:
                st.warning("⚠️  Bản dịch hiện tại sẽ bị **ghi đè**.")

            update_data = False
            force_scout = False
            with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
                c1, c2 = st.columns(2)
                update_data = c1.checkbox(
                    "Cập nhật nhân vật/từ điển sau khi dịch",
                    help="Tự động cập nhật data nhân vật và thuật ngữ mới.",
                )
                force_scout = c2.checkbox(
                    "Chạy Scout AI trước",
                    help="Scout đọc chương gần đây để cập nhật ngữ cảnh.",
                )

            rt_alive = S.rt_running and S.rt_thread is not None and \
                       getattr(S.rt_thread, "is_alive", lambda: False)()

            if not rt_alive:
                if st.button("⚡ Xác nhận dịch lại", type="primary", key="tx_rt_confirm"):
                    from littrans.ui.core.state import reset_job
                    reset_job(S, "rt")
                    S.rt_logs = []
                    S.rt_q    = queue.Queue()
                    from littrans.ui.runner import run_background
                    S.rt_thread = run_background(
                        S.rt_q, mode="retranslate", novel_name=S.current_novel,
                        filename=ch["name"], update_data=update_data,
                        force_scout=force_scout,
                        all_files=[c["name"] for c in load_chapters(S.current_novel)],
                        chapter_index=ch["idx"],
                    )
                    S.rt_running  = True
                    S.rt_last_log = time.time()
                    st.rerun()
            else:
                st.info("⏳ Đang dịch lại… (có thể chuyển tab khác)")

            if S.rt_running or S.rt_logs:
                with st.expander("📋 Nhật ký", expanded=bool(S.rt_running)):
                    _show_log(S.rt_logs)

            if (not S.rt_running) and S.rt_logs and not S.get("_rt_post_clear_done"):
                load_chapters.clear(); load_stats.clear()
                S["_rt_post_clear_done"] = True
            if S.rt_running:
                S["_rt_post_clear_done"] = False
