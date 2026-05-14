"""Tests for plain-text / BBCode / EPUB / ZIP exporters."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ebooklib import epub

from trilex.output import (
    chapter_to_bbcode,
    chapter_to_plain_text,
    export_epub,
    export_vault_zip,
)
from trilex.output import (
    write_chapter as vault_write_chapter,
)
from trilex.persistence.models import Chapter, Project


def _make_chapter(
    *,
    index: int,
    polished: str | None = "Lý Thanh bước vào Thanh Vân Tông.",
    source: str = "李青走进青云宗。",
    convert: str | None = "Lý Thanh đi vào Thanh Vân Tông.",
    title: str | None = "Mở Đầu",
    state: str = "polished",
) -> Chapter:
    return Chapter(
        project_id="p1",
        index=index,
        source_text=source,
        convert_text=convert,
        polished_text=polished,
        state=state,
        title=title,
        tokens_used=128,
        provider_used="gemini-3.1-flash-lite",
        warnings=[],
        translated_at=datetime.now(UTC),
    )


def _make_project() -> Project:
    return Project(
        name="Đại Đạo",
        slug="dai-dao",
        source_lang="zh",
        target_lang="vn",
        genre="tu_tien",
    )


# --------------------------------------------------------------------------- #
# Plain text                                                                  #
# --------------------------------------------------------------------------- #


def test_plain_text_returns_body_with_title_prefix() -> None:
    ch = _make_chapter(index=1, title="Khởi đầu", polished="Câu một.\n\nCâu hai.")
    out = chapter_to_plain_text(ch)
    assert out.startswith("Khởi đầu")
    assert "Câu một." in out
    assert "Câu hai." in out
    # No frontmatter / callouts / markdown leaked in.
    assert "---" not in out
    assert "[!" not in out
    assert "#" not in out


def test_plain_text_falls_back_when_no_polish() -> None:
    ch = _make_chapter(index=1, polished=None, convert="Convert only.", title=None)
    assert chapter_to_plain_text(ch) == "Convert only."


def test_plain_text_handles_empty_chapter() -> None:
    ch = _make_chapter(index=1, polished=None, convert=None, source="", title=None)
    assert chapter_to_plain_text(ch) == ""


# --------------------------------------------------------------------------- #
# BBCode                                                                      #
# --------------------------------------------------------------------------- #


def test_bbcode_wraps_header_and_body() -> None:
    ch = _make_chapter(index=47, title="Khảo hạch")
    bb = chapter_to_bbcode(ch)
    assert bb.startswith("[b][size=14]Chương 47 — Khảo hạch[/size][/b]")
    assert "Lý Thanh" in bb
    assert "[spoiler" not in bb  # not requested


def test_bbcode_includes_source_and_convert_when_requested() -> None:
    ch = _make_chapter(index=1)
    bb = chapter_to_bbcode(ch, include_source=True, include_convert=True)
    assert "[spoiler=Bản gốc]" in bb
    assert "李青" in bb
    assert "[spoiler=Bản convert]" in bb
    assert "[/spoiler]" in bb


# --------------------------------------------------------------------------- #
# EPUB                                                                        #
# --------------------------------------------------------------------------- #


def test_export_epub_creates_valid_file(tmp_path: Path) -> None:
    project = _make_project()
    chapters = [
        _make_chapter(index=i, title=f"Ch {i}", polished=f"Nội dung chương {i}.") for i in (1, 2, 3)
    ]
    out = tmp_path / "dai-dao.epub"
    written = export_epub(project, chapters, out)
    assert written == out
    assert out.exists()
    assert out.stat().st_size > 1024  # non-trivial size

    # Round-trip read with ebooklib to confirm it parses.
    book = epub.read_epub(str(out))
    titles = book.get_metadata("DC", "title")
    assert titles[0][0] == "Đại Đạo"
    # 3 chapters + nav + ncx + css
    html_items = list(book.get_items_of_type(9))  # ITEM_DOCUMENT
    chapter_items = [i for i in html_items if "chapters/" in i.file_name]
    assert len(chapter_items) == 3


def test_export_epub_orders_chapters_by_index(tmp_path: Path) -> None:
    project = _make_project()
    # Pass chapters out of order — exporter must sort.
    chapters = [_make_chapter(index=i) for i in (3, 1, 2)]
    out = tmp_path / "ordered.epub"
    export_epub(project, chapters, out)
    book = epub.read_epub(str(out))
    chapter_files = sorted(
        i.file_name for i in book.get_items_of_type(9) if "chapters/" in i.file_name
    )
    assert chapter_files == [
        "chapters/0001.xhtml",
        "chapters/0002.xhtml",
        "chapters/0003.xhtml",
    ]


def test_export_epub_escapes_html_special_chars(tmp_path: Path) -> None:
    project = _make_project()
    ch = _make_chapter(index=1, polished="<script>alert('x')</script> & <b>bold</b>")
    out = tmp_path / "esc.epub"
    export_epub(project, [ch], out)
    book = epub.read_epub(str(out))
    chap = next(i for i in book.get_items_of_type(9) if "chapters/" in i.file_name)
    body = chap.get_content().decode("utf-8")
    assert "&lt;script&gt;" in body
    assert "<script>alert" not in body


# --------------------------------------------------------------------------- #
# Vault ZIP                                                                   #
# --------------------------------------------------------------------------- #


def test_export_vault_zip_round_trips(tmp_path: Path) -> None:
    # Build a fake vault with 3 chapter files via the obsidian writer.
    vault = tmp_path / "vault"
    for i in (1, 2, 3):
        vault_write_chapter(vault, "dai-dao", _make_chapter(index=i))

    out = tmp_path / "vault.zip"
    written, count = export_vault_zip(vault, "dai-dao", out)
    assert written == out
    assert count >= 3
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert any("chapters/0001.md" in n for n in names)
    assert all(n.startswith("dai-dao/") for n in names)


def test_export_vault_zip_missing_folder_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_vault_zip(tmp_path, "no-such-project", tmp_path / "x.zip")
