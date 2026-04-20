"""
src/littrans/tools/epub_exporter.py — Translated chapters → .epub (Phase 6).

Usage:
    from littrans.tools.epub_exporter import export_to_epub, EpubExportMeta, get_translated_chapters
    import io
    chapters = get_translated_chapters("my_novel")
    buf = io.BytesIO()
    export_to_epub(chapters, buf, EpubExportMeta(title="My Novel"))
    # buf.getvalue() → bytes for st.download_button

BytesIO output avoids writing temp files — safe for concurrent Streamlit users.
"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO


@dataclass
class EpubExportMeta:
    title   : str
    author  : str = "Unknown"
    language: str = "vi"


def export_to_epub(
    chapters : list[Path],
    output   : str | Path | BytesIO | BinaryIO,
    meta     : EpubExportMeta,
) -> None:
    """Build epub from sorted *_VN.txt paths and write to output.

    output accepts:
      str | Path  → write file to disk
      BytesIO     → write in-memory (use .getvalue() for st.download_button)
    """
    try:
        from ebooklib import epub
    except ImportError:
        raise ImportError("pip install ebooklib")

    book = epub.EpubBook()
    book.set_identifier(f"novelpipeline-{int(time.time())}")
    book.set_title(meta.title)
    book.set_language(meta.language)
    book.add_author(meta.author)

    # Cover page
    cover = epub.EpubHtml(title=meta.title, file_name="cover.xhtml", lang=meta.language)
    cover.content = (
        '<html><body style="text-align:center;margin-top:30%;font-family:serif">'
        f'<h1 style="font-size:2em">{html.escape(meta.title)}</h1>'
        f'<p style="color:#555">{html.escape(meta.author)}</p>'
        "</body></html>"
    )
    book.add_item(cover)

    chapter_items: list = []
    for idx, path in enumerate(chapters, 1):
        ch_title, body = _parse_vn_file(path)
        c = epub.EpubHtml(
            title=ch_title,
            file_name=f"chap_{idx:04d}.xhtml",
            lang=meta.language,
        )
        c.content = (
            "<html><body>"
            f"<h1>{html.escape(ch_title)}</h1>"
            f"{_text_to_html(body)}"
            "</body></html>"
        )
        book.add_item(c)
        chapter_items.append(c)

    book.toc = tuple(chapter_items)
    book.spine = ["nav", cover, *chapter_items]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(output, book)


def get_translated_chapters(novel_name: str = "") -> list[Path]:
    """Return sorted *_VN.txt from outputs/{novel_name}/."""
    try:
        from littrans.config.settings import settings
        out_dir = settings.active_output_dir
    except Exception:
        out_dir = Path("outputs") / novel_name if novel_name else Path("outputs")

    if not out_dir.exists():
        return []
    files = sorted(
        [f for f in out_dir.iterdir() if f.name.endswith("_VN.txt")],
        key=lambda f: [int(t) if t.isdigit() else t.lower()
                       for t in re.split(r"(\d+)", f.name)],
    )
    return files


def _parse_vn_file(path: Path) -> tuple[str, str]:
    """(title, body). Title = first non-empty line (stripped of #), else filename."""
    text   = path.read_text(encoding="utf-8", errors="replace").strip()
    lines  = text.splitlines()
    title  = ""
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            title = stripped[:120]
            body_start = i + 1
            break
    if not title:
        title = path.stem.replace("_VN", "").replace("_", " ")
    body = "\n".join(lines[body_start:]).strip()
    return title, body


def _text_to_html(text: str) -> str:
    """Plain text / simple markdown → HTML. html.escape first, then markdown."""
    paras = re.split(r"\n{2,}", text)
    out: list[str] = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if re.match(r"^-{3,}$", p):
            out.append("<hr/>")
            continue
        # html.escape before applying markdown (escapes < > & but NOT *)
        p = html.escape(p)
        # Bold and italic
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p, flags=re.DOTALL)
        p = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", p, flags=re.DOTALL)
        # Single newlines → <br>
        p = p.replace("\n", "<br>\n")
        out.append(f"<p>{p}</p>")
    return "\n".join(out) if out else "<p></p>"
