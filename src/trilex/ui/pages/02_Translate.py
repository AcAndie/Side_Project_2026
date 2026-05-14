"""Translate page — 3 tabs: Single Chapter / Batch / From URL (stub)."""

from __future__ import annotations

import streamlit as st

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline import translate_chapter
from trilex.core.style_pack import StylePackError, get_style_pack
from trilex.persistence.repos import ProjectRepo
from trilex.ui._helpers import (
    db_ready,
    gemini_provider_or_warn,
    get_session_maker,
    run_async,
    sidebar_project_selector,
)
from trilex.ui.runners import (
    persist_chapter_result,
    submit_batch,
)

st.set_page_config(page_title="Translate — TriLex", page_icon="✨", layout="wide")

sidebar_project_selector()

st.title("✨ Translate")

if not db_ready():
    st.error("DB chưa init. Chạy `trilex db init`.")
    st.stop()

active = st.session_state.get("active_project_id")
if active is None:
    st.warning("Chưa chọn project. Mở **Library** để tạo và switch project.")
    st.stop()


async def _fetch_active():
    async with get_session_maker()() as s:
        return await ProjectRepo(s).get(active)


project = run_async(_fetch_active())
if project is None:
    st.error("Project đã chọn không tồn tại. Reset.")
    st.session_state.pop("active_project_id", None)
    st.stop()

st.info(
    f"📂 **{project.name}** · {project.source_lang}→{project.target_lang} · "
    f"genre `{project.genre}` · vault `{project.vault_path or 'data/vault'}`"
)

tab_single, tab_batch, tab_url = st.tabs(["📝 Single Chapter", "📚 Batch", "🌐 From URL"])

# --------------------------------------------------------------------------- #
# Tab 1 — single chapter (synchronous, with Save button)                      #
# --------------------------------------------------------------------------- #

with tab_single:
    cols = st.columns(3)
    mode = cols[0].selectbox(
        "Mode",
        ["polish", "convert", "side_by_side"],
        key="single_mode",
        help="convert = QT pass only. polish = + LLM. side_by_side = both visible.",
    )
    title = cols[1].text_input("Title (optional)", key="single_title")
    save_to_vault = cols[2].checkbox("Save to vault sau khi dịch", value=True, key="single_save")

    uploaded = st.file_uploader("Hoặc upload .txt", type=["txt"], key="single_file")
    if uploaded is not None:
        prefill = uploaded.getvalue().decode("utf-8", errors="replace")
    else:
        prefill = st.session_state.get("single_text", "")

    source_text = st.text_area(
        "Nội dung chương",
        value=prefill,
        height=260,
        placeholder="Paste 1 chương ZH/EN tại đây...",
        key="single_text",
    )

    if st.button(
        "🚀 Translate Now",
        type="primary",
        disabled=not source_text.strip(),
        key="single_run",
    ):
        try:
            get_style_pack(project.genre, project.target_lang)  # type: ignore[arg-type]
        except StylePackError as e:
            st.error(f"Style pack `{project.genre}.{project.target_lang}` thiếu: {e}")
            st.stop()

        provider = None
        if mode != "convert":
            provider = gemini_provider_or_warn()
            if provider is None:
                st.stop()

        cfg = ProjectConfig(
            source_lang=project.source_lang,  # type: ignore[arg-type]
            target_lang=project.target_lang,  # type: ignore[arg-type]
            genre=project.genre,
        )
        with st.spinner(f"Đang dịch ({mode}) ~15–40s..."):
            try:
                result = run_async(
                    translate_chapter(
                        source_text,
                        cfg,
                        mode=mode,  # type: ignore[arg-type]
                        provider=provider,
                    )
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"Dịch thất bại: {type(e).__name__}: {e}")
                st.stop()

        st.session_state["single_last_result"] = result
        st.session_state["single_last_title"] = title.strip() or None
        st.session_state["single_last_save"] = save_to_vault

    last = st.session_state.get("single_last_result")
    if last is not None:
        if last.state == "failed":
            st.error("Pipeline state=failed")
            for w in last.warnings:
                st.write(f"- {w}")
        else:
            st.success(f"Done — {last.total_elapsed_ms:.0f}ms · {last.tokens_used} tokens")
            if last.mode == "side_by_side":
                cols = st.columns(3)
                cols[0].subheader("Source")
                cols[0].code(last.source_text, language=None)
                cols[1].subheader("Convert")
                cols[1].code(last.convert_text or "(no QT pass)", language=None)
                cols[2].subheader("Polish")
                cols[2].code(last.final_text, language=None)
            else:
                cols = st.columns(2)
                cols[0].subheader("Original")
                cols[0].code(last.source_text, language=None)
                cols[1].subheader("Polished" if last.mode == "polish" else "Convert")
                cols[1].code(last.final_text, language=None)

            if last.warnings:
                with st.expander(f"⚠️ {len(last.warnings)} warnings"):
                    for w in last.warnings:
                        st.write(f"- {w}")

            scol1, scol2 = st.columns([1, 3])
            if scol1.button("💾 Save to project", type="primary", key="single_save_btn"):
                try:
                    chapter_id, idx, vault_path = persist_chapter_result(
                        project.id,
                        last,
                        title=st.session_state.get("single_last_title"),
                        write_to_vault=st.session_state.get("single_last_save", True),
                    )
                except Exception as e:  # noqa: BLE001
                    st.error(f"Save thất bại: {type(e).__name__}: {e}")
                else:
                    msg = f"Saved as chương {idx} (id {chapter_id[:8]}…)"
                    if vault_path is not None:
                        msg += f" → `{vault_path}`"
                    st.success(msg)
                    # Clear the buffered result so we don't double-save by accident.
                    st.session_state.pop("single_last_result", None)

# --------------------------------------------------------------------------- #
# Tab 2 — batch (background thread, monitor in Jobs page)                     #
# --------------------------------------------------------------------------- #

with tab_batch:
    st.caption(
        "Upload nhiều file .txt — mỗi file = 1 chương. Dịch chạy nền, theo dõi ở tab **Jobs**."
    )
    cols = st.columns(3)
    b_mode = cols[0].selectbox("Mode", ["polish", "convert", "side_by_side"], key="batch_mode")
    b_save = cols[1].checkbox("Save to vault", value=True, key="batch_save")
    cols[2].caption("Filename → chapter title. Thứ tự index tự tăng theo project.")

    batch_files = st.file_uploader(
        "Files .txt",
        type=["txt"],
        accept_multiple_files=True,
        key="batch_files",
    )

    if batch_files:
        st.write(f"Đã chọn **{len(batch_files)}** file:")
        for f in batch_files:
            st.write(f"- `{f.name}` ({len(f.getvalue()):,} bytes)")

    if st.button(
        "🚀 Submit batch",
        type="primary",
        disabled=not batch_files,
        key="batch_submit",
    ):
        if b_mode != "convert" and gemini_provider_or_warn() is None:
            st.stop()

        chapters: list[tuple[str | None, str]] = []
        for f in batch_files:
            text = f.getvalue().decode("utf-8", errors="replace").strip()
            if not text:
                continue
            chapters.append((f.name.rsplit(".", 1)[0], text))

        if not chapters:
            st.error("Tất cả file đều rỗng.")
            st.stop()

        try:
            job_id = submit_batch(
                project.id,
                chapters,
                mode=b_mode,
                write_to_vault=b_save,
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"Submit thất bại: {type(e).__name__}: {e}")
        else:
            st.success(
                f"Đã submit job `{job_id[:8]}…` cho {len(chapters)} chương. "
                "Mở tab **Jobs** để theo dõi."
            )

# --------------------------------------------------------------------------- #
# Tab 3 — URL ingest (stub)                                                   #
# --------------------------------------------------------------------------- #

with tab_url:
    st.info(
        "🚧 Tính năng URL ingest sẽ làm sau khi scrapers module xong. "
        "Hiện tại dùng tab **Single Chapter** hoặc **Batch** (paste/upload .txt)."
    )
    url = st.text_input(
        "URL chương (sẽ implement)",
        placeholder="https://example.com/novel/chapter-1",
        disabled=True,
    )
    st.button("Fetch & translate", disabled=True)
    st.markdown(
        "**Roadmap**: site profile system "
        "(Qidian / 69shu / SFACG / RoyalRoad / generic AI-learned)."
    )
