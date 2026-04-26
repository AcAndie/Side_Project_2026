"""
src/littrans/ui/pages/export_page.py — Tab Export (Phase 3, NEW).

Three sections:
  1. EPUB Processor — upload .epub → split into inputs/{novel}/*.md
  2. Xuất bản dịch — EPUB / MD-zip download for translated novel
  3. Bible Export — markdown / json / timeline / characters / consistency
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from littrans.ui.epub_ui import render_epub_tab


def render_export(S: Any) -> None:
    import streamlit as st

    st.subheader("📦 Export")
    st.caption(
        "Một nơi cho mọi loại xuất file: EPUB processor (upload .epub), xuất bản dịch "
        "(EPUB / MD), và Bible Export (markdown / json / timeline)."
    )

    sections = st.tabs([
        "📚 EPUB Processor",
        "📖 Xuất bản dịch",
        "📜 Bible Export",
    ])

    with sections[0]:
        # Reuse existing EPUB processor UI
        render_epub_tab(S)

    with sections[1]:
        _render_translation_export(S)

    with sections[2]:
        _render_bible_export(S)


# ── Translation export (EPUB + MD-zip) ───────────────────────────

def _render_translation_export(S: Any) -> None:
    import streamlit as st

    novel = S.get("current_novel") or ""
    if not novel:
        st.info(
            "Chưa chọn truyện. Quay lại 🏠 Thư viện để chọn truyện trước khi export."
        )
        return

    try:
        from littrans.config.settings import settings
        out_dir: Path = settings.active_output_dir
    except Exception:
        out_dir = Path("outputs") / novel

    if not out_dir.exists():
        st.warning(f"Chưa có bản dịch nào trong `{out_dir}`. Dịch trước khi export.")
        return

    vn_files = sorted(out_dir.glob("*_VN.txt"))
    st.caption(f"📁 `{out_dir}` — {len(vn_files)} bản dịch sẵn sàng.")

    if not vn_files:
        st.info("Chưa có file *_VN.txt nào trong outputs/.")
        return

    # ── EPUB ──────────────────────────────────────────────────
    st.markdown("### 📕 Xuất EPUB")
    c1, c2 = st.columns(2)
    epub_title  = c1.text_input(
        "Tiêu đề", key="export_epub_title",
        value=novel.replace("_", " ").title(),
    )
    epub_author = c2.text_input("Tác giả", value="Unknown", key="export_epub_author")

    if st.button("🔄 Tạo EPUB", key="export_epub_gen", type="primary"):
        try:
            from littrans.tools.epub_exporter import (
                export_to_epub, EpubExportMeta, get_translated_chapters,
            )
            chaps = get_translated_chapters(novel)
            if not chaps:
                st.error("Không tìm thấy file *_VN.txt.")
            else:
                buf = io.BytesIO()
                export_to_epub(
                    chaps, buf,
                    EpubExportMeta(
                        title=epub_title or novel,
                        author=epub_author or "Unknown",
                    ),
                )
                S["epub_export_bytes"] = buf.getvalue()
                S["epub_export_novel"] = novel
                st.success(f"✅ EPUB từ {len(chaps)} chương sẵn sàng download.")
        except Exception as exc:
            st.error(f"❌ Lỗi xuất EPUB: {exc}")

    if S.get("epub_export_bytes") and S.get("epub_export_novel") == novel:
        st.download_button(
            "⬇️ Download EPUB",
            data=S["epub_export_bytes"],
            file_name=f"{novel or 'novel'}.epub",
            mime="application/epub+zip",
            key="export_epub_dl",
        )

    st.divider()

    # ── MD zip ────────────────────────────────────────────────
    st.markdown("### 📄 Xuất MD (zip toàn bộ chương)")
    if st.button("🔄 Tạo zip", key="export_md_zip"):
        try:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for fp in vn_files:
                    zf.write(fp, arcname=fp.name)
            S["md_zip_bytes"] = buf.getvalue()
            S["md_zip_novel"] = novel
            st.success(f"✅ Zip {len(vn_files)} chương sẵn sàng download.")
        except Exception as exc:
            st.error(f"❌ Lỗi tạo zip: {exc}")

    if S.get("md_zip_bytes") and S.get("md_zip_novel") == novel:
        st.download_button(
            "⬇️ Download zip",
            data=S["md_zip_bytes"],
            file_name=f"{novel}_translations.zip",
            mime="application/zip",
            key="export_md_zip_dl",
        )


# ── Bible export (delegates to bible_page.render_bible_export) ───

def _render_bible_export(S: Any) -> None:
    import streamlit as st

    try:
        from littrans.config.settings import settings
        if not settings.bible_available:
            st.info(
                "Bible chưa được khởi tạo cho truyện này. "
                "Mở tab 📖 Bible để khởi tạo và chạy scan trước khi export."
            )
            return
    except Exception as exc:
        st.error(f"Settings lỗi: {exc}")
        return

    from littrans.ui.pages.bible_page import render_bible_export
    render_bible_export(S)
