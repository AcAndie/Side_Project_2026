"""
src/littrans/ui/scraper_page.py — Web Novel Scraper UI page (Phase 4).
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


def render_scraper(S: Any) -> None:
    import streamlit as st

    st.subheader("🌐 Cào Truyện")
    st.caption(
        "Scrape web novel → chapters tại `inputs/{tên_truyện}/` sẵn sàng cho pipeline dịch."
    )

    for key, default in [
        ("scraper_running",         False),
        ("scraper_q",               None),
        ("scraper_logs",            []),
        ("scraper_result",          None),
        ("_scraper_result_holder",  []),
        ("_scraper_novel_name",     ""),
    ]:
        if key not in S:
            S[key] = default

    urls_text = st.text_area(
        "URL truyện (1/dòng — hỗ trợ `!relearn domain.com`)",
        height=150,
        placeholder=(
            "https://royalroad.com/fiction/12345/story-name\n"
            "https://novelfire.net/...\n"
            "!relearn royalroad.com  ← force re-learn domain"
        ),
        key="scraper_urls_input",
    )

    auto_name = _auto_detect_name(urls_text or "")
    novel_name = st.text_input(
        "Tên truyện (ghi vào `inputs/{tên}/`)",
        value=auto_name,
        placeholder="vd: wandering_inn",
        key="scraper_novel_name_input",
    )

    col1, col2 = st.columns(2)
    fast_learning = col1.checkbox(
        "Fast learning (bỏ optimizer)",
        key="scraper_fast",
        help="Bỏ optimizer — nhanh hơn nhưng profile kém chính xác",
    )
    validation = col2.checkbox(
        "Validation (ProseRichness)",
        value=True,
        key="scraper_valid",
        help="Bật validation chất lượng nội dung trích xuất",
    )
    max_pw = st.number_input(
        "Playwright concurrency",
        min_value=1,
        max_value=8,
        value=2,
        key="scraper_max_pw",
        help="Số instance Playwright chạy song song",
    )

    col_btn, col_info = st.columns([1, 3])

    if not S.scraper_running:
        has_urls = bool(urls_text and urls_text.strip())
        has_name = bool(novel_name and novel_name.strip())
        start_ok = has_urls and has_name

        if col_btn.button("🚀 Bắt đầu cào", type="primary", disabled=not start_ok):
            raw_lines   = [l.strip() for l in urls_text.strip().splitlines() if l.strip()]
            relearn     = [l.split()[-1] for l in raw_lines if l.startswith("!relearn ")]
            scrape_urls = [l for l in raw_lines if not l.startswith("!")]

            S["scraper_logs"]           = []
            S["scraper_q"]              = queue.Queue()
            S["scraper_result"]         = None
            S["_scraper_result_holder"] = []
            S["_scraper_novel_name"]    = novel_name.strip()

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
                progress_queue=S["scraper_q"],
                result_holder=S["_scraper_result_holder"],
            )
            runner.start()
            S["scraper_running"] = True
            st.rerun()

        if not has_urls:
            col_info.info("💡 Nhập URL truyện để bắt đầu.")
        elif not has_name:
            col_info.warning("⚠️ Điền tên truyện trước khi cào.")
    else:
        col_btn.button("⏳ Đang cào…", disabled=True)
        col_info.warning("🔄 Đang chạy — đừng đóng cửa sổ.")

    if S.scraper_running or S.scraper_logs:
        _handle_log(S)

    result = S.get("scraper_result")
    if result is not None:
        _render_result(S, result)


def _handle_log(S: Any) -> None:
    import streamlit as st
    from littrans.ui.runner import poll_queue

    if S.scraper_running:
        done, _ = poll_queue(S.scraper_q, S.scraper_logs)
        if done:
            S["scraper_running"] = False
            result_holder = S.get("_scraper_result_holder", [])
            if result_holder:
                S["scraper_result"] = result_holder[0]
            ok = S.get("scraper_result")
            S.scraper_logs.append("─" * 56)
            S.scraper_logs.append(
                "✅ Cào hoàn tất!" if (ok and ok.ok) else "⚠️ Hoàn tất có lỗi."
            )

    if S.scraper_logs:
        with st.expander("📋 Nhật ký cào", expanded=bool(S.scraper_running)):
            st.code("\n".join(S.scraper_logs[-300:]), language=None)

    if S.scraper_running:
        time.sleep(1.0)
        st.rerun()


def _render_result(S: Any, result: Any) -> None:
    import streamlit as st

    if result.ok:
        st.success(
            f"✅ Cào xong **{result.chapters_written}** chương → `{result.output_dir}`"
        )
        col_a, _ = st.columns([1, 4])
        if col_a.button("🇻🇳 Sang tab Dịch", key="scraper_go_translate"):
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
    else:
        st.error(f"❌ Có lỗi: {'; '.join(result.errors[:3])}")
        if result.chapters_written > 0:
            st.info(
                f"Đã ghi được {result.chapters_written} chương trước khi gặp lỗi."
            )
