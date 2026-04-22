"""
src/littrans/ui/pipeline_page.py — Pipeline UI page (Phase 5).
1-click workflow: scrape / EPUB → inputs/ → translate → outputs/
"""
from __future__ import annotations

import queue
import time
from pathlib import Path
from typing import Any

_MODES = {
    "web_only"       : "🌐 Chỉ cào web → .md",
    "epub_only"      : "📚 Chỉ xử lý EPUB → .md",
    "web_translate"  : "🌐→🇻🇳 Cào web + dịch",
    "epub_translate" : "📚→🇻🇳 Xử lý EPUB + dịch",
    "file_translate" : "📂→🇻🇳 Dịch file có sẵn",
}


def _stage_count(mode: str) -> int:
    return 2 if mode in ("web_translate", "epub_translate") else 1


def _stage_label(mode: str, stage: int) -> str:
    labels: dict[str, list[str]] = {
        "web_only"       : ["① Đang cào web…"],
        "epub_only"      : ["① Đang xử lý EPUB…"],
        "web_translate"  : ["① Đang cào web…", "② Đang dịch…"],
        "epub_translate" : ["① Đang xử lý EPUB…", "② Đang dịch…"],
        "file_translate" : ["① Đang dịch…"],
    }
    opts = labels.get(mode, ["① Đang xử lý…"])
    return opts[min(max(stage - 1, 0), len(opts) - 1)]


def render_pipeline(S: Any) -> None:
    import streamlit as st

    st.subheader("🚀 Pipeline")
    st.caption("1-click workflow: nguồn → `inputs/` → dịch → `outputs/`")

    for key, default in [
        ("pipeline_running",  False),
        ("pipeline_q",        None),
        ("pipeline_logs",     []),
        ("pipeline_stage",    0),    # 0=idle 1=stage1 2=stage2 99=done
        ("_pl_mode",          ""),
        ("_pl_novel_name",    ""),
        ("_pl_result_holder", []),
        ("_pl_epub_path",     ""),
    ]:
        if key not in S:
            S[key] = default

    # ── Mode selector ──────────────────────────────────────────────
    mode = st.radio(
        "Chế độ",
        list(_MODES.keys()),
        format_func=lambda k: _MODES[k],
        horizontal=True,
        key="pl_mode_radio",
        disabled=S.pipeline_running,
    )

    st.divider()

    col_src, col_cfg = st.columns(2)

    with col_src:
        if mode in ("web_only", "web_translate"):
            urls_text = st.text_area(
                "URL truyện (1/dòng, hỗ trợ `!relearn domain`)",
                height=120,
                placeholder="https://royalroad.com/fiction/...",
                key="pl_urls",
                disabled=S.pipeline_running,
            )
            epub_file = None
        elif mode in ("epub_only", "epub_translate"):
            epub_file = st.file_uploader(
                "File EPUB",
                type=["epub"],
                key="pl_epub_upload",
                disabled=S.pipeline_running,
            )
            urls_text = ""
        else:  # file_translate
            st.info("Dịch từ chương đã có trong `inputs/{tên_truyện}/`.")
            urls_text = ""
            epub_file = None

    with col_cfg:
        auto_name = _auto_name(
            mode,
            urls_text if mode in ("web_only", "web_translate") else "",
            epub_file.name if epub_file else "",
        )
        novel_name = st.text_input(
            "Tên truyện",
            value=auto_name,
            placeholder="vd: wandering_inn",
            key="pl_novel_name",
            disabled=S.pipeline_running,
        )
        if novel_name:
            st.caption(f"Chương vào `inputs/{novel_name}/`")

        if mode in ("web_only", "web_translate"):
            max_pw = st.number_input(
                "Playwright concurrency", min_value=1, max_value=8, value=2,
                key="pl_max_pw", disabled=S.pipeline_running,
            )
        else:
            max_pw = 2

    # ── Stage progress ─────────────────────────────────────────────
    if S.pipeline_running or S.pipeline_stage > 0:
        pl_mode = S.get("_pl_mode", mode) or mode
        stage   = S.pipeline_stage
        total   = _stage_count(pl_mode)
        if stage == 99:
            st.progress(1.0, text="✅ Hoàn tất")
        elif stage > 0:
            st.progress(
                min((stage - 0.5) / total, 1.0),
                text=_stage_label(pl_mode, stage),
            )

    # ── Run button ─────────────────────────────────────────────────
    col_btn, col_info = st.columns([1, 3])

    if not S.pipeline_running:
        has_src  = _has_source(
            mode,
            urls_text if mode in ("web_only", "web_translate") else None,
            epub_file if mode in ("epub_only", "epub_translate") else None,
        )
        has_name = bool(novel_name and novel_name.strip())

        if col_btn.button("🚀 Chạy", type="primary", disabled=not (has_src and has_name)):
            _launch(
                S, mode,
                urls_text if mode in ("web_only", "web_translate") else "",
                epub_file,
                novel_name.strip(),
                int(max_pw),
            )

        if not has_src:
            col_info.info("💡 Nhập URL hoặc upload EPUB để bắt đầu.")
        elif not has_name:
            col_info.warning("⚠️ Điền tên truyện.")
    else:
        col_btn.button("⏳ Đang chạy…", disabled=True)
        col_info.warning("🔄 Pipeline đang chạy — đừng đóng cửa sổ.")

    if S.pipeline_running or S.pipeline_logs:
        _handle_log(S)

    if not S.pipeline_running and S.pipeline_stage == 99:
        _render_result(S)


def _auto_name(mode: str, urls_text: str, epub_filename: str) -> str:
    from urllib.parse import urlparse
    if mode in ("epub_only", "epub_translate") and epub_filename:
        return Path(epub_filename).stem.replace("-", "_")[:40]
    for line in urls_text.strip().splitlines():
        line = line.strip()
        if line.startswith("http"):
            try:
                parts = [s for s in urlparse(line).path.strip("/").split("/") if s]
                if parts:
                    return parts[-1].replace("-", "_")[:40]
            except Exception:
                pass
    return ""


def _has_source(mode: str, urls_text: str | None, epub_file: Any) -> bool:
    if mode in ("web_only", "web_translate"):
        return bool(urls_text and urls_text.strip())
    if mode in ("epub_only", "epub_translate"):
        return epub_file is not None
    return True  # file_translate uses existing inputs/


def _launch(
    S: Any, mode: str, urls_text: str, epub_file: Any,
    novel_name: str, max_pw: int,
) -> None:
    import streamlit as st

    S["pipeline_logs"]     = []
    S["pipeline_q"]        = queue.Queue()
    S["pipeline_stage"]    = 1
    S["_pl_mode"]          = mode
    S["_pl_novel_name"]    = novel_name
    S["_pl_result_holder"] = []
    S["_pl_epub_path"]     = ""

    urls: list[str] = []
    epub_path = ""

    if mode in ("web_only", "web_translate"):
        urls = [l.strip() for l in urls_text.strip().splitlines()
                if l.strip() and not l.strip().startswith("!")]

    elif mode in ("epub_only", "epub_translate") and epub_file is not None:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            suffix=".epub", delete=False, prefix=f"np_{novel_name}_",
        )
        tmp.write(epub_file.getvalue())
        tmp.flush()
        tmp.close()
        epub_path = tmp.name
        S["_pl_epub_path"] = epub_path

    from littrans.ui.runner import PipelineRunner
    runner = PipelineRunner(
        mode=mode,
        urls=urls,
        epub_path=epub_path,
        novel_name=novel_name,
        max_pw=max_pw,
        progress_queue=S["pipeline_q"],
        result_holder=S["_pl_result_holder"],
    )
    runner.start()
    S["pipeline_running"] = True
    st.rerun()


def _handle_log(S: Any) -> None:
    import streamlit as st
    from littrans.ui.runner import poll_queue

    if S.pipeline_running:
        done, extras = poll_queue(
            S.pipeline_q, S.pipeline_logs,
            extra_markers=("__STAGE_2__", "__STAGE_DONE__"),
        )
        for m in extras:
            if m == "__STAGE_2__":
                S["pipeline_stage"] = 2
            elif m == "__STAGE_DONE__":
                S["pipeline_stage"] = 99

        if done:
            S["pipeline_running"] = False
            if S.pipeline_stage != 99:
                S["pipeline_stage"] = 99
            S.pipeline_logs.append("─" * 56)
            S.pipeline_logs.append("✅ Pipeline hoàn tất!")
            _cleanup_epub(S)

    if S.pipeline_logs:
        with st.expander("📋 Nhật ký pipeline", expanded=bool(S.pipeline_running)):
            st.code("\n".join(S.pipeline_logs[-300:]), language=None)

    if S.pipeline_running:
        time.sleep(1.0)
        st.rerun()


def _cleanup_epub(S: Any) -> None:
    path = S.get("_pl_epub_path", "")
    if path:
        try:
            import os
            os.unlink(path)
        except Exception:
            pass
        S["_pl_epub_path"] = ""


def _render_result(S: Any) -> None:
    import streamlit as st

    mode    = S.get("_pl_mode", "")
    novel   = S.get("_pl_novel_name", "")
    results = S.get("_pl_result_holder", [])

    st.success("✅ Pipeline hoàn tất!")

    for tag, result in results:
        if tag == "scrape":
            st.info(f"🌐 Cào: **{result.chapters_written}** chương → `{result.output_dir}`")
        elif tag == "epub":
            st.info(f"📚 EPUB: **{result.chapters_written}** chương → `{result.output_dir}`")

    if mode in ("web_translate", "epub_translate", "file_translate"):
        col_a, _ = st.columns([1, 4])
        if col_a.button("📄 Sang tab Dịch", key="pl_go_translate"):
            if novel:
                try:
                    from littrans.config.settings import set_novel
                    set_novel(novel)
                    S["current_novel"] = novel
                except Exception:
                    pass
            S["page"] = "translate"
            st.rerun()
