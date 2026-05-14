"""Export page — per-chapter copy/.txt + project-level EPUB / vault ZIP."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from sqlalchemy import asc, select

from trilex.output import (
    chapter_to_bbcode,
    chapter_to_plain_text,
    chapters_for_export,
    export_epub,
    export_vault_zip,
)
from trilex.persistence.models import Chapter
from trilex.persistence.repos import ProjectRepo
from trilex.ui._helpers import (
    db_ready,
    get_session_maker,
    run_async,
    sidebar_project_selector,
)

st.set_page_config(page_title="Export — TriLex", page_icon="📤", layout="wide")
sidebar_project_selector()

st.title("📤 Export")

if not db_ready():
    st.error("DB chưa init. Chạy `trilex db init`.")
    st.stop()

active = st.session_state.get("active_project_id")
if active is None:
    st.warning("Chọn project ở sidebar.")
    st.stop()


async def _fetch():
    async with get_session_maker()() as s:
        project = await ProjectRepo(s).get(active)
        if project is None:
            return None, []
        result = await s.execute(
            select(Chapter).where(Chapter.project_id == active).order_by(asc(Chapter.index))
        )
        return project, list(result.scalars())


project, all_chapters = run_async(_fetch())
if project is None:
    st.error("Project không tồn tại.")
    st.stop()

usable = chapters_for_export(all_chapters)
st.caption(
    f"Project **{project.name}** — {len(all_chapters)} chương trong DB, "
    f"{len(usable)} có nội dung export."
)

# --------------------------------------------------------------------------- #
# Per-chapter                                                                 #
# --------------------------------------------------------------------------- #

st.header("📝 Per-chapter")

if not usable:
    st.info("Chưa có chương nào sẵn sàng export.")
else:
    options = {f"{int(c.index):04d} — {c.title or '(no title)'}": c for c in usable}
    label = st.selectbox("Chọn chương", list(options.keys()), key="export_pick_chapter")
    chosen = options[label]

    tab_plain, tab_bbcode, tab_meta = st.tabs(["Plain text", "BBCode (forum)", "Stats"])

    with tab_plain:
        plain = chapter_to_plain_text(chosen)
        st.caption("Copy bằng icon 📋 ở góc, hoặc nhấn nút Download.")
        st.code(plain, language=None, wrap_lines=True)
        st.download_button(
            "⬇️ Download .txt",
            data=plain.encode("utf-8"),
            file_name=f"{project.slug}_{int(chosen.index):04d}.txt",
            mime="text/plain",
            key=f"dl_plain_{chosen.id}",
        )

    with tab_bbcode:
        cols = st.columns(2)
        inc_src = cols[0].checkbox("Kèm bản gốc trong spoiler", value=False)
        inc_conv = cols[1].checkbox("Kèm bản convert trong spoiler", value=False)
        bb = chapter_to_bbcode(chosen, include_source=inc_src, include_convert=inc_conv)
        st.caption("Forum-ready BBCode. Copy icon ở góc trên.")
        st.code(bb, language=None, wrap_lines=True)
        st.download_button(
            "⬇️ Download .bbcode.txt",
            data=bb.encode("utf-8"),
            file_name=f"{project.slug}_{int(chosen.index):04d}.bbcode.txt",
            mime="text/plain",
            key=f"dl_bb_{chosen.id}",
        )

    with tab_meta:
        st.write("**Index**:", int(chosen.index))
        st.write("**State**:", chosen.state)
        st.write("**Tokens used**:", chosen.tokens_used)
        st.write("**Provider**:", chosen.provider_used or "—")
        st.write("**Translated at**:", chosen.translated_at)
        if chosen.warnings:
            st.write("**Warnings**:")
            for w in chosen.warnings:
                st.write(f"  - {w}")

st.divider()

# --------------------------------------------------------------------------- #
# Project-level                                                               #
# --------------------------------------------------------------------------- #

st.header("📦 Per-project")

cols = st.columns(2)

# EPUB
with cols[0]:
    st.subheader("📖 EPUB")
    st.caption(f"{len(usable)} chương sẽ được đóng gói. Mở bằng Calibre / Apple Books / KOReader.")
    epub_out = Path("data/exports") / f"{project.slug}.epub"
    if st.button(
        "Build EPUB",
        type="primary",
        disabled=not usable,
        key="build_epub",
    ):
        try:
            export_epub(project, usable, epub_out)
        except Exception as e:  # noqa: BLE001
            st.error(f"EPUB build thất bại: {type(e).__name__}: {e}")
        else:
            st.success(f"Đã ghi: `{epub_out.resolve()}`")
    if epub_out.exists():
        with epub_out.open("rb") as f:
            st.download_button(
                "⬇️ Download EPUB",
                data=f.read(),
                file_name=epub_out.name,
                mime="application/epub+zip",
                key="dl_epub",
            )
        st.caption(f"File size: {epub_out.stat().st_size / 1024:.1f} KB")

# ZIP
with cols[1]:
    st.subheader("🗜️ Vault ZIP")
    st.caption(
        "Đóng gói toàn bộ markdown files trong vault folder (chapters/, characters/, ..) "
        "thành 1 .zip — để backup hoặc share Obsidian vault."
    )
    vault_root = Path(project.vault_path) if project.vault_path else Path("data/vault")
    zip_out = Path("data/exports") / f"{project.slug}.zip"
    vault_proj = vault_root / "projects" / project.slug
    if not vault_proj.exists():
        st.info(f"Vault folder chưa tồn tại: `{vault_proj}`")
    if st.button(
        "Build ZIP",
        type="primary",
        disabled=not vault_proj.exists(),
        key="build_zip",
    ):
        try:
            _, count = export_vault_zip(vault_root, project.slug, zip_out)
        except FileNotFoundError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"ZIP build thất bại: {type(e).__name__}: {e}")
        else:
            st.success(f"Đã ghi: `{zip_out.resolve()}` ({count} files)")
    if zip_out.exists():
        with zip_out.open("rb") as f:
            st.download_button(
                "⬇️ Download ZIP",
                data=f.read(),
                file_name=zip_out.name,
                mime="application/zip",
                key="dl_zip",
            )
        st.caption(f"File size: {zip_out.stat().st_size / 1024:.1f} KB")
