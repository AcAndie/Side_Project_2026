"""src/littrans/ui/pages/glossary_page.py — Từ điển page."""
from __future__ import annotations

import queue
import time

import pandas as pd
import streamlit as st

from littrans.ui.loaders import load_glossary_data, load_stats
from littrans.ui.ui_utils import _poll, _show_log


def render_glossary() -> None:
    S = st.session_state
    glos = load_glossary_data(S.current_novel)

    if not glos:
        st.info("**Từ điển trống.** Thuật ngữ tự thu thập khi dịch. "
                "Sau vài chương, nhấn **🔄 Phân loại** để sắp xếp vào đúng danh mục.")
        return

    staging_n = len(glos.get("staging", []))
    if staging_n:
        st.info(f"📖 **{staging_n} thuật ngữ mới** đang chờ phân loại. "
                "Nhấn **🔄 Phân loại** để AI sắp xếp vào đúng danh mục.")

    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    sel_cat = c1.selectbox("Danh mục", ["Tất cả"] + list(glos.keys()),
                           label_visibility="collapsed", key="glos_cat")
    search  = c2.text_input("🔍", placeholder="Tìm thuật ngữ...",
                             label_visibility="collapsed", key="glos_q")
    with c3:
        if not S.clean_running:
            if st.button("🔄 Phân loại", disabled=not staging_n,
                         help="AI phân loại Staging vào đúng danh mục"):
                S.clean_logs = []; S.clean_q = queue.Queue()
                from littrans.ui.runner import run_background
                run_background(S.clean_q, mode="clean_glossary", novel_name=S.current_novel)
                S.clean_running = True; st.rerun()
        else:
            st.button("⏳ …", disabled=True, key="clean_busy")
    with c4:
        if st.button("↺ Làm mới", key="glos_refresh"):
            load_glossary_data.clear(); st.rerun()

    _cat_label = {"pathways":"Tu luyện","organizations":"Tổ chức","items":"Vật phẩm",
                  "locations":"Địa danh","general":"Chung","staging":"⏳ Chờ phân loại"}
    rows = []
    for cat, entries in glos.items():
        if sel_cat != "Tất cả" and cat != sel_cat: continue
        for eng, vn in entries:
            if search and search.lower() not in eng.lower() and search.lower() not in vn.lower():
                continue
            rows.append({"Tiếng Anh": eng, "Tiếng Việt": vn, "Danh mục": _cat_label.get(cat, cat)})

    if rows:
        st.caption(f"{len(rows)} thuật ngữ")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={"Danh mục": st.column_config.TextColumn(width="small")})
    else:
        st.info("Không tìm thấy thuật ngữ nào.")

    if S.clean_running or S.clean_logs:
        if S.clean_running:
            if _poll("clean_q", "clean_logs"):
                S.clean_running = False
                S.clean_logs.append("✅ Phân loại hoàn tất.")
                load_glossary_data.clear(); load_stats.clear()
        with st.expander("📋 Nhật ký", expanded=S.clean_running):
            _show_log(S.clean_logs)
        if S.clean_running:
            time.sleep(0.9); st.rerun()
