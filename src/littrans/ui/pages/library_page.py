"""
ui/pages/library_page.py — Landing page: thư viện truyện dạng card grid.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime


def _novel_stats(root: Path, name: str) -> dict:
    nd = root / "inputs" / name
    od = root / "outputs" / name
    total = 0
    done  = 0
    last_mtime = 0.0
    if nd.exists():
        for f in nd.iterdir():
            if f.suffix in (".txt", ".md") and not f.name.startswith("."):
                total += 1
                last_mtime = max(last_mtime, f.stat().st_mtime)
    if od.exists():
        for f in od.iterdir():
            if f.name.endswith("_VN.txt"):
                done += 1
                last_mtime = max(last_mtime, f.stat().st_mtime)
    return {
        "total"     : total,
        "done"      : done,
        "last_time" : last_mtime,
        "has_output": od.exists(),
    }


def render_library() -> None:
    import streamlit as st
    from littrans.ui.env_utils import _get_available_novels, _apply_novel

    S = st.session_state
    root = Path(__file__).resolve().parents[4]

    st.markdown("## 📚 Thư viện truyện")
    st.caption("Chọn truyện để dịch — hoặc tạo mới bằng tab Cào / Export (EPUB).")

    novels = _get_available_novels()
    if not novels:
        st.info(
            "Chưa có truyện nào trong `inputs/`. "
            "Dùng tab **🌐 Cào** (web → inputs) hoặc **📦 Export** (EPUB → inputs)."
        )
        col1, col2 = st.columns(2)
        if col1.button("🌐 Cào Truyện", use_container_width=True, type="primary"):
            S.page = "scrape"; st.rerun()
        if col2.button("📦 EPUB → chương", use_container_width=True):
            S.page = "export"; st.rerun()
        return

    # Grid 3 cột — Streamlit columns thay cho pure CSS grid để button work
    ncols = 3
    for i in range(0, len(novels), ncols):
        cols = st.columns(ncols)
        for j, name in enumerate(novels[i:i + ncols]):
            with cols[j]:
                stats = _novel_stats(root, name)
                total = stats["total"] or 1
                pct   = int(100 * stats["done"] / total)
                last  = (
                    datetime.fromtimestamp(stats["last_time"]).strftime("%Y-%m-%d %H:%M")
                    if stats["last_time"] else "—"
                )
                # Card container
                with st.container(border=True):
                    st.markdown(f"**📖 {name}**")
                    st.caption(f"{stats['done']}/{stats['total']} chương • {last}")
                    st.progress(min(pct / 100, 1.0))
                    c1, c2 = st.columns(2)
                    if c1.button("🇻🇳 Dịch", key=f"lib_t_{name}", use_container_width=True, type="primary"):
                        S.current_novel = name
                        _apply_novel(name)
                        S.sel_ch = 0
                        S.page = "translate"
                        st.rerun()
                    if c2.button("🔍 Xem", key=f"lib_v_{name}", use_container_width=True):
                        S.current_novel = name
                        _apply_novel(name)
                        S.sel_ch = 0
                        S.page = "translate"  # reader is now inside Dịch tab
                        st.rerun()

    st.divider()
    cc1, cc2 = st.columns(2)
    if cc1.button("🌐 Cào web → truyện mới", use_container_width=True, type="primary"):
        S.page = "scrape"; st.rerun()
    if cc2.button("📦 EPUB → chương", use_container_width=True):
        S.page = "export"; st.rerun()
