"""EPUB exporter — bundle a project's polished chapters into a single .epub.

Wraps `ebooklib`. The output validates in Calibre / Apple Books / KOReader.
Each Chapter becomes one EpubHtml entry in the spine; TOC is generated from
chapter.title (falls back to "Chương N").
"""

from __future__ import annotations

import html
import logging
import uuid
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

from ebooklib import epub

from trilex.persistence.models import Chapter, Project

logger = logging.getLogger(__name__)

LANG_TO_BCP47: dict[str, str] = {"vn": "vi", "en": "en", "zh": "zh"}


def _chapter_html(chapter: Chapter) -> str:
    """Render polished text as minimal XHTML — each blank-line-split paragraph
    becomes one `<p>` tag. Everything is HTML-escaped."""
    title = html.escape(chapter.title or f"Chương {int(chapter.index)}")
    body = (chapter.polished_text or chapter.convert_text or chapter.source_text or "").strip()
    if not body:
        body_html = "<p><em>(empty)</em></p>"
    else:
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        body_html = "\n".join(
            f"<p>{html.escape(p).replace(chr(10), '<br/>')}</p>" for p in paragraphs
        )
    return (
        f"<html xmlns='http://www.w3.org/1999/xhtml'>"
        f"<head><title>{title}</title>"
        f"<link rel='stylesheet' type='text/css' href='style/main.css'/></head>"
        f"<body><h1>{title}</h1>{body_html}</body></html>"
    )


def export_epub(
    project: Project,
    chapters: Sequence[Chapter],
    out_path: Path,
    *,
    author: str = "TriLex",
) -> Path:
    """Write the project's chapters into one EPUB file. Returns `out_path`."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    book = epub.EpubBook()
    book.set_identifier(f"trilex-{project.slug}-{uuid.uuid4()}")
    book.set_title(project.name)
    book.set_language(LANG_TO_BCP47.get(project.target_lang, project.target_lang))
    book.add_author(author)
    book.add_metadata("DC", "publisher", "TriLex")
    book.add_metadata(
        "DC",
        "description",
        f"Auto-translated by TriLex ({project.source_lang} → {project.target_lang}).",
    )

    sorted_chapters = sorted(chapters, key=lambda c: int(c.index))
    epub_items: list[epub.EpubHtml] = []

    css = epub.EpubItem(
        uid="style",
        file_name="style/main.css",
        media_type="text/css",
        content=(
            "body { font-family: serif; line-height: 1.6; margin: 1em; }\n"
            "h1 { font-size: 1.4em; margin-bottom: 1em; }\n"
            "p { margin: 0 0 0.8em 0; text-indent: 1.5em; }\n"
        ),
    )
    book.add_item(css)

    for ch in sorted_chapters:
        item = epub.EpubHtml(
            title=ch.title or f"Chương {int(ch.index)}",
            file_name=f"chapters/{int(ch.index):04d}.xhtml",
            lang=LANG_TO_BCP47.get(project.target_lang, project.target_lang),
        )
        item.content = _chapter_html(ch)
        item.add_item(css)
        book.add_item(item)
        epub_items.append(item)

    book.toc = tuple(epub_items)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *epub_items]

    epub.write_epub(str(out_path), book, {})
    logger.info("Wrote EPUB: %s (%d chapters)", out_path, len(epub_items))
    return out_path


def export_vault_zip(
    vault_root: Path,
    project_slug: str,
    out_path: Path,
) -> tuple[Path, int]:
    """Zip the project's vault folder into `out_path`. Returns
    `(out_path, file_count)`. Skips if the vault folder doesn't exist."""
    src = Path(vault_root) / "projects" / project_slug
    if not src.exists():
        raise FileNotFoundError(f"Vault project folder not found: {src}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in src.rglob("*"):
            if path.is_file():
                arcname = Path(project_slug) / path.relative_to(src)
                zf.write(path, arcname=arcname.as_posix())
                count += 1
    logger.info("Wrote ZIP: %s (%d files)", out_path, count)
    return out_path, count


def chapters_for_export(items: Iterable[Chapter]) -> list[Chapter]:
    """Filter to chapters that actually have output. Caller-friendly helper."""
    return [c for c in items if (c.polished_text or c.convert_text or c.source_text)]
