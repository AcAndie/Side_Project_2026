"""src/littrans/ui/pages/stats_page.py — Thống kê page."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from littrans.ui.loaders import load_chapters, load_stats


def render_stats() -> None:
    S = st.session_state
    s        = load_stats(S.current_novel)
    chapters = load_chapters(S.current_novel)
    done  = sum(1 for c in chapters if c["done"])
    total = len(chapters)

    st.subheader("📊 Tổng quan")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chương đã dịch", f"{done} / {total}",
              delta=f"{int(done/total*100)}%" if total else None)
    m2.metric("Nhân vật theo dõi",  s["chars"].get("active",  0),
              help="Nhân vật xuất hiện gần đây")
    m3.metric("Nhân vật lưu trữ",   s["chars"].get("archive", 0),
              help="Tự động archive sau N chương vắng mặt")
    em = s["chars"].get("emotional", 0)
    m4.metric("Trạng thái đặc biệt", em,
              delta="cần chú ý" if em else None, delta_color="inverse",
              help="Tức giận / tổn thương / vừa thay đổi — ảnh hưởng lời thoại")

    st.divider()
    glos          = s.get("glos", {})
    total_terms   = sum(v for k, v in glos.items() if k != "staging")
    staging_terms = glos.get("staging", 0)
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Thuật ngữ từ điển", total_terms)
    m6.metric("Chờ phân loại",     staging_terms,
              delta="→ Tab Từ điển" if staging_terms else None, delta_color="inverse")
    m7.metric("Kỹ năng đã biết",   s["skills"].get("total", 0))
    m8.metric("Tên đã chốt",        s["lock"].get("total_locked", 0),
              help="Name Lock — tên có bản dịch cố định, không thay đổi")

    chart_data = {k: v for k, v in glos.items() if v and k != "staging"}
    if chart_data:
        st.divider()
        st.markdown("**Phân bổ từ điển theo danh mục**")
        cat_vn = {"pathways":"Tu luyện","organizations":"Tổ chức",
                  "items":"Vật phẩm","locations":"Địa danh","general":"Chung"}
        df = pd.DataFrame.from_dict(
            {cat_vn.get(k, k): v for k, v in chart_data.items()},
            orient="index", columns=["Thuật ngữ"],
        )
        st.bar_chart(df, color="#3B6D11")

    if total:
        st.divider()
        st.progress(done / total, text=f"Tiến độ: {done}/{total} · {int(done/total*100)}%")
        rows = [{"Chương": c["name"],
                 "Trạng thái": "✅ Đã dịch" if c["done"] else "⬜ Chưa",
                 "Kích thước": c["size"]} for c in chapters]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
