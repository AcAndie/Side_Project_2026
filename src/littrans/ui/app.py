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

from littrans.ui.bible_ui                import render_bible_tab   as render_bible
from littrans.ui.epub_ui                 import render_epub_tab    as render_epub
from littrans.ui.scraper_page            import render_scraper
from littrans.ui.pipeline_page           import render_pipeline
from littrans.ui.pages.welcome_page      import render_welcome
from littrans.ui.pages.translate_page    import render_translate
from littrans.ui.pages.chapters_page     import render_chapters
from littrans.ui.pages.characters_page   import render_characters
from littrans.ui.pages.glossary_page     import render_glossary
from littrans.ui.pages.stats_page        import render_stats
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
_DEFAULTS: dict[str, Any] = {
    "page"                  : "translate",
    "running"               : False,
    "run_thread"            : None,
    "log_q"                 : None,
    "logs"                  : [],
    "rt_running"            : False,
    "rt_thread"             : None,
    "rt_q"                  : None,
    "rt_logs"               : [],
    "sel_ch"                : 0,
    "show_rt"               : False,
    "clean_running"         : False,
    "clean_q"               : None,
    "clean_logs"            : [],
    "chars_action_running"  : False,
    "chars_action_q"        : None,
    "chars_action_logs"     : [],
    "settings_saved"        : False,
    "current_novel"         : "",
    "bible_scan_running"    : False,
    "bible_scan_q"          : None,
    "bible_scan_logs"       : [],
    "bible_crossref_running": False,
    "bible_crossref_q"      : None,
    "bible_crossref_logs"   : [],
    "bible_export_done"     : False,
    "epub_running"          : False,
    "epub_q"                : None,
    "epub_logs"             : [],
    "last_export_file"      : None,
    "epub_export_bytes"     : None,
    "epub_export_novel"     : "",
    "pipeline_running"      : False,
    "pipeline_q"            : None,
    "pipeline_logs"         : [],
    "pipeline_stage"        : 0,
    "_pl_mode"              : "",
    "_pl_novel_name"        : "",
    "_pl_result_holder"     : [],
    "_pl_epub_path"         : "",
    "scraper_running"           : False,
    "scraper_q"                 : None,
    "scraper_logs"              : [],
    "scraper_result"            : None,
    "_scraper_result_holder"    : [],
    "_scraper_novel_name"       : "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""<style>
.badge{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin:1px}
.badge-ok  {background:#EAF3DE;color:#3B6D11}
.badge-warn{background:#FAEEDA;color:#633806}
.badge-err {background:#FCEBEB;color:#791F1F}
.badge-info{background:#E6F1FB;color:#0C447C}
.badge-dim {background:#F1EFE8;color:#444441}
.strong-lock{color:#3B6D11;font-size:11px}
.weak-lock  {color:#BA7517;font-size:11px}
.welcome-card{background:linear-gradient(135deg,#EEEDFE 0%,#E6F1FB 100%);
  border-radius:16px;padding:32px;margin-bottom:24px;border:1px solid #d0cef8}
.step-card{background:white;border-radius:12px;padding:20px;border:1px solid #e8e8e8;height:100%}
.step-num{width:32px;height:32px;border-radius:50%;background:#3C3489;color:white;
  display:inline-flex;align-items:center;justify-content:center;
  font-weight:700;font-size:14px;margin-bottom:8px}
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
        S.sel_ch = 0; S.logs = []; S.rt_logs = []; st.rerun()
    elif not S.current_novel:
        S.current_novel = selected; _apply_novel(selected)


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
        st.caption("v5.7 — LitRPG / Tu Tiên Pipeline")
        st.divider()

        _render_novel_selector()
        st.divider()

        _pages = {
            "pipeline"  : "🚀 Pipeline",
            "scraper"   : "🌐 Cào Truyện",
            "translate" : "📄 Dịch",
            "chapters"  : "🔍 Xem chương",
            "characters": "👤 Nhân vật",
            "glossary"  : "📚 Từ điển",
            "stats"     : "📊 Thống kê",
            "settings"  : "⚙️ Cài đặt",
            "bible"     : "📖 Bible System",
            "epub"      : "📚 EPUB",
        }
        for key, label in _pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if S.page == key else "secondary"):
                S.page = key; S.show_rt = False; st.rerun()

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
            (S.pipeline_running,     "🚀 Đang pipeline…"),
            (S.scraper_running,      "🌐 Đang cào…"),
            (S.running,              "🔄 Đang dịch…"),
            (S.rt_running,           "↺ Đang dịch lại…"),
            (S.clean_running,        "🔄 Đang phân loại…"),
            (S.chars_action_running, "👤 Đang xử lý nhân vật…"),
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

    _route = {
        "pipeline"  : lambda: render_pipeline(S),
        "scraper"   : lambda: render_scraper(S),
        "translate" : render_translate,
        "chapters"  : render_chapters,
        "characters": render_characters,
        "glossary"  : render_glossary,
        "stats"     : render_stats,
        "settings"  : render_settings,
        "bible"     : lambda: render_bible(S),
        "epub"      : lambda: render_epub(S),
    }
    _route.get(S.page, render_translate)()


main()
