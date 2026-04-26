"""src/littrans/ui/app.py — LiTTrans Web UI (Streamlit) v5.7 — router only."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
for _p in [str(_ROOT), str(_ROOT / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

from littrans.ui.pages.welcome_page      import render_welcome
from littrans.ui.pages.library_page      import render_library
from littrans.ui.pages.scrape_page       import render_scrape
from littrans.ui.pages.translate_page    import render_translate
from littrans.ui.pages.bible_page        import render_bible
from littrans.ui.pages.export_page       import render_export
from littrans.ui.pages.settings_page     import render_settings
from littrans.ui.env_utils import _has_api_key, _get_available_novels, _apply_novel
from littrans.ui.loaders   import load_chapters

st.set_page_config(
    page_title="LiTTrans — Dịch Truyện Tự Động",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────
# Job state uses unified prefix scheme via core.state.JOB_KEYS.
# Non-job keys (UI selections, artifacts) listed here.
from littrans.ui.core.state import init_all_jobs

_DEFAULTS: dict[str, Any] = {
    "page"                  : "library",
    "sel_ch"                : 0,
    "show_rt"               : False,
    "settings_saved"        : False,
    "current_novel"         : "",
    "bible_export_done"     : False,
    # Artifacts (not job state)
    "last_export_file"      : None,
    "epub_export_bytes"     : None,
    "epub_export_novel"     : "",
    "md_zip_bytes"          : None,
    "md_zip_novel"          : "",
    # Scraper artifacts (the *job* state lives under sc_*)
    "scraper_result"            : None,
    "_scraper_result_holder"    : [],
    "_scraper_novel_name"       : "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

init_all_jobs(st.session_state)

# ── CSS (dark-first) ──────────────────────────────────────────────
st.markdown("""<style>
.badge{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin:1px}
.badge-ok  {background:#1f3a1f;color:#8FD67C}
.badge-warn{background:#3a2d14;color:#F0B969}
.badge-err {background:#3a1717;color:#F28787}
.badge-info{background:#152a3d;color:#7DB8F0}
.badge-dim {background:#252830;color:#A0A4AB}
.strong-lock{color:#8FD67C;font-size:11px}
.weak-lock  {color:#F0B969;font-size:11px}
.welcome-card{background:linear-gradient(135deg,#1E1F3D 0%,#15253A 100%);
  border-radius:16px;padding:32px;margin-bottom:24px;border:1px solid #2f3160}
.step-card{background:#1A1F2A;border-radius:12px;padding:20px;border:1px solid #2a2f3a;height:100%}
.step-num{width:32px;height:32px;border-radius:50%;background:#6B5EF5;color:white;
  display:inline-flex;align-items:center;justify-content:center;
  font-weight:700;font-size:14px;margin-bottom:8px}

/* Top nav */
.topnav{display:flex;gap:6px;padding:8px 0 14px;border-bottom:1px solid #2a2f3a;margin-bottom:18px;flex-wrap:wrap}
.topnav .stButton button{border-radius:8px;font-weight:600}

/* Library cards */
.lib-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
.lib-card{background:#1A1F2A;border:1px solid #2a2f3a;border-radius:12px;padding:16px;
  transition:transform .15s,border-color .15s;cursor:pointer}
.lib-card:hover{transform:translateY(-2px);border-color:#6B5EF5}
.lib-title{font-weight:700;font-size:15px;color:#E6E8EB;margin-bottom:8px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lib-meta{font-size:12px;color:#A0A4AB;margin-bottom:10px}
.lib-bar{height:6px;background:#252830;border-radius:3px;overflow:hidden}
.lib-bar-fill{height:100%;background:linear-gradient(90deg,#6B5EF5,#8B7EF8)}

/* Reader typography */
.reader-container{max-width:720px;margin:0 auto;padding:0 8px}
.reader-text{font-family:Georgia,'Times New Roman',serif;line-height:1.8;font-size:17px;color:#D8DCE1}
.reader-text p{margin:0 0 1em}
</style>""", unsafe_allow_html=True)


# ── Novel selector (sidebar) ──────────────────────────────────────

def _render_novel_selector() -> None:
    S = st.session_state
    novels = _get_available_novels()
    if not novels:
        st.sidebar.caption("📁 **Một truyện** (flat mode)\n\n"
                           "_Tạo subfolder trong `inputs/` để quản lý nhiều truyện._")
        if S.current_novel:
            S.current_novel = ""; _apply_novel("")
        return

    current  = S.current_novel if S.current_novel in novels else novels[0]
    selected = st.sidebar.selectbox(
        "📚 Truyện đang chọn", novels,
        index=novels.index(current) if current in novels else 0,
        key="novel_selector_sb",
        help="Mỗi truyện có data riêng biệt (nhân vật, từ điển, bộ nhớ).",
    )
    if selected != S.current_novel:
        S.current_novel = selected; _apply_novel(selected)
        S.sel_ch = 0; S.tx_logs = []; S.rt_logs = []; st.rerun()
    elif not S.current_novel:
        S.current_novel = selected; _apply_novel(selected)


# ── Top nav (Phase 3: 5 tabs + Library) ───────────────────────────

_NAV = [
    ("library",   "🏠 Thư viện"),
    ("scrape",    "🌐 Cào"),
    ("translate", "🇻🇳 Dịch"),
    ("bible",     "📖 Bible"),
    ("export",    "📦 Export"),
    ("settings",  "⚙️ Cài đặt"),
]


def _render_top_nav() -> None:
    S = st.session_state
    cols = st.columns(len(_NAV))
    for col, (key, label) in zip(cols, _NAV):
        with col:
            if st.button(
                label, key=f"topnav_{key}", use_container_width=True,
                type="primary" if S.page == key else "secondary",
            ):
                S.page = key; S.show_rt = False; st.rerun()
    st.markdown(
        "<div style='height:8px;border-bottom:1px solid #2a2f3a;margin-bottom:14px'></div>",
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────

def main() -> None:
    S = st.session_state

    if not _has_api_key():
        with st.sidebar:
            st.markdown("## 📖 LiTTrans")
            st.caption("v5.7 — Thiết lập ban đầu")
        render_welcome()
        return

    with st.sidebar:
        st.markdown("## 📖 LiTTrans")
        st.caption("v5.7")
        st.divider()

        _render_novel_selector()
        st.divider()

        try:
            chs   = load_chapters(S.current_novel)
            done  = sum(1 for c in chs if c["done"])
            total = len(chs)
            if total:
                st.progress(done / total)
                st.caption(f"{done}/{total} chương")
            elif S.current_novel:
                st.caption(f"📁 {S.current_novel} — chưa có chương")

            try:
                from littrans.context.glossary import glossary_stats
                stg_n = glossary_stats().get("staging", 0)
                if stg_n:
                    st.markdown(
                        f'<span class="badge badge-warn">📖 {stg_n} thuật ngữ chờ phân loại</span>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass

            try:
                from littrans.context.characters import has_staging_chars
                sc = has_staging_chars()
                if sc:
                    st.markdown(
                        f'<span class="badge badge-info">👤 {sc} nhân vật chờ merge</span>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass
        except Exception:
            pass

        for flag, msg in [
            (S.get("sc_running"), "🌐 Đang cào…"),
            (S.get("tx_running"), "🔄 Đang dịch…"),
            (S.get("rt_running"), "↺ Đang dịch lại…"),
            (S.get("bi_running"), "📖 Đang scan Bible…"),
            (S.get("ep_running"), "📚 Đang xử lý EPUB…"),
            (S.get("cg_running"), "🔄 Đang phân loại từ điển…"),
            (S.get("cc_running"), "👤 Đang xử lý nhân vật…"),
        ]:
            if flag:
                st.warning(msg)

        st.divider()
        if _has_api_key():
            st.caption("✅ API key đã cài đặt")
        else:
            st.caption("⚠️ Chưa có API key")
            if st.button("🔑 Cài đặt API Key", key="sidebar_setup"):
                S.page = "settings"; st.rerun()

    if S.current_novel:
        try:
            from littrans.config.settings import settings, set_novel
            if settings.novel_name != S.current_novel:
                set_novel(S.current_novel)
        except Exception:
            pass

    _render_top_nav()

    # ── Global polling: drain ALL job queues regardless of current tab ──
    # Replaces per-page poll/rerun loops (Phase 2). Threads keep running
    # when user switches tabs; logs catch up on every rerun.
    from littrans.ui.core.jobs import poll_all
    import time as _time
    _active = poll_all(S)

    _route = {
        "library"   : render_library,
        "scrape"    : lambda: render_scrape(S),
        "translate" : render_translate,
        "bible"     : lambda: render_bible(S),
        "export"    : lambda: render_export(S),
        "settings"  : render_settings,
    }
    _route.get(S.page, render_library)()

    if _active:
        _time.sleep(0.9)
        st.rerun()


main()
