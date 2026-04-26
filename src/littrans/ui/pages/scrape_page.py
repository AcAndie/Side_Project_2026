"""
src/littrans/ui/pages/scrape_page.py — Tab Cào (Phase 3 rebuild).

Merges legacy scraper_page + pipeline_page web_only mode. Single responsibility:
URL → inputs/{novel}/{chapter}.md via async scraper + auto learning.
"""
from __future__ import annotations

import queue
import time
from typing import Any
from urllib.parse import urlparse


def _auto_detect_name(urls_text: str) -> str:
    for line in urls_text.strip().splitlines():
        line = line.strip()
        if line.startswith("http") and not line.startswith("!"):
            try:
                parts = [s for s in urlparse(line).path.strip("/").split("/") if s]
                if parts:
                    return parts[-1].replace("-", "_")[:40]
            except Exception:
                pass
    return ""


def render_scrape(S: Any) -> None:
    import streamlit as st

    st.subheader("🌐 Cào Truyện")
    st.caption(
        "Scrape web novel → chapters tại `inputs/{tên_truyện}/`. Lần đầu cho mỗi domain "
        "AI sẽ tự động học cấu trúc — về sau cào nhanh không tốn token."
    )

    for key, default in [
        ("scraper_result",          None),
        ("_scraper_result_holder",  []),
        ("_scraper_novel_name",     ""),
    ]:
        if key not in S:
            S[key] = default

    urls_text = st.text_area(
        "URL truyện (1/dòng — hỗ trợ `!relearn domain.com`)",
        height=140,
        placeholder=(
            "https://royalroad.com/fiction/12345/story-name\n"
            "https://novelfire.net/...\n"
            "!relearn royalroad.com  ← force re-learn domain"
        ),
        key="scrape_urls_input",
    )

    auto_name = _auto_detect_name(urls_text or "")
    novel_name = st.text_input(
        "Tên truyện (ghi vào `inputs/{tên}/`)",
        value=S.get("_scraper_novel_name") or auto_name,
        placeholder="vd: wandering_inn",
        key="scrape_novel_name_input",
    )

    with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
        col1, col2 = st.columns(2)
        fast_learning = col1.checkbox(
            "Fast learning (bỏ optimizer)",
            key="scrape_fast",
            help="Bỏ optimizer — nhanh hơn nhưng profile kém chính xác",
        )
        validation = col2.checkbox(
            "Validation (ProseRichness)",
            value=True,
            key="scrape_valid",
            help="Bật validation chất lượng nội dung trích xuất",
        )
        max_pw = st.number_input(
            "Playwright concurrency",
            min_value=1, max_value=8, value=2,
            key="scrape_max_pw",
            help="Số instance Playwright chạy song song",
        )

    col_btn, col_info = st.columns([1, 3])

    sc_alive = S.sc_running and S.sc_thread is not None and \
               getattr(S.sc_thread, "is_alive", lambda: False)()

    if not sc_alive:
        has_urls = bool(urls_text and urls_text.strip())
        has_name = bool(novel_name and novel_name.strip())
        start_ok = has_urls and has_name

        if col_btn.button("🚀 Bắt đầu cào", type="primary", disabled=not start_ok):
            raw_lines   = [l.strip() for l in urls_text.strip().splitlines() if l.strip()]
            relearn     = [l.split()[-1] for l in raw_lines if l.startswith("!relearn ")]
            scrape_urls = [l for l in raw_lines if not l.startswith("!")]

            from littrans.ui.core.state import reset_job
            reset_job(S, "sc")

            S["scraper_result"]         = None
            S["_scraper_result_holder"] = []
            S["_scraper_novel_name"]    = novel_name.strip()
            S.sc_logs = []
            S.sc_q    = queue.Queue()

            from littrans.ui.runner import ScrapeRunner
            from littrans.modules.scraper import ScraperOptions

            opts = ScraperOptions(
                novel_name=novel_name.strip(),
                fast_learning=fast_learning,
                validation=validation,
                max_pw_instances=int(max_pw),
                relearn_domains=relearn,
            )
            runner = ScrapeRunner(
                urls=scrape_urls,
                options=opts,
                progress_queue=S.sc_q,
                result_holder=S["_scraper_result_holder"],
            )
            runner.start()
            S.sc_thread   = runner
            S.sc_running  = True
            S.sc_last_log = time.time()
            st.rerun()

        if not has_urls:
            col_info.info("💡 Nhập URL truyện để bắt đầu.")
        elif not has_name:
            col_info.warning("⚠️ Điền tên truyện trước khi cào.")
    else:
        col_btn.button("⏳ Đang cào…", disabled=True)
        col_info.warning("🔄 Đang chạy — đừng đóng cửa sổ. (Có thể chuyển tab khác)")

    err = S.get("sc_error")
    if err:
        st.error(f"❌ Scraper lỗi: {err}")

    if S.sc_logs:
        with st.expander("📋 Nhật ký cào", expanded=bool(S.sc_running)):
            st.code("\n".join(S.sc_logs[-300:]), language=None)

    if (not S.sc_running) and S.get("scraper_result") is None:
        holder = S.get("_scraper_result_holder") or []
        if holder:
            S["scraper_result"] = holder[0]

    result = S.get("scraper_result")
    if result is not None and not S.sc_running:
        _render_result(S, result)


def _render_result(S: Any, result: Any) -> None:
    import streamlit as st

    if result.ok:
        st.success(
            f"✅ Cào xong **{result.chapters_written}** chương → `{result.output_dir}`"
        )
        col_a, col_b = st.columns([1, 1])
        if col_a.button("🇻🇳 Sang tab Dịch", key="scrape_go_translate"):
            novel = S.get("_scraper_novel_name", "")
            if novel:
                try:
                    from littrans.config.settings import set_novel
                    set_novel(novel)
                    S["current_novel"] = novel
                except Exception:
                    pass
            S["page"] = "translate"
            st.rerun()
        if col_b.button("🌐 Cào tiếp", key="scrape_again"):
            S["scraper_result"] = None
            S["_scraper_result_holder"] = []
            st.rerun()
    else:
        st.error(f"❌ Có lỗi: {'; '.join(result.errors[:3])}")
        if result.chapters_written > 0:
            st.info(
                f"Đã ghi được {result.chapters_written} chương trước khi gặp lỗi."
            )
