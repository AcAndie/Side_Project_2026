"""Tests for the Obsidian vault writer."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from trilex.core.models.character import Character
from trilex.output.obsidian import (
    PROJECT_SUBDIRS,
    ensure_vault_structure,
    project_root,
    write_chapter,
    write_character,
    write_project_dashboard,
)
from trilex.persistence.models import Chapter


def _make_chapter(
    *,
    index: int,
    source_text: str = "李青走进青云宗。",
    convert_text: str | None = "Lý Thanh đi vào Thanh Vân Tông .",
    polished_text: str | None = "Lý Thanh bước vào Thanh Vân Tông.",
    state: str = "polished",
    title: str | None = None,
    tokens_used: int = 128,
    provider_used: str | None = "gemini-3.1-flash-lite",
    warnings: list[str] | None = None,
    translated_at: datetime | None = None,
) -> Chapter:
    """Build a transient Chapter (no DB session)."""
    return Chapter(
        project_id="proj-1",
        index=index,
        source_text=source_text,
        convert_text=convert_text,
        polished_text=polished_text,
        state=state,
        title=title,
        tokens_used=tokens_used,
        provider_used=provider_used,
        warnings=warnings or [],
        translated_at=translated_at or datetime.now(UTC),
    )


def _parse_frontmatter(md_text: str) -> dict:
    assert md_text.startswith("---\n"), "missing frontmatter opener"
    _, fm, _ = md_text.split("---", 2)
    return yaml.safe_load(fm)


# --------------------------------------------------------------------------- #
# Folder layout                                                               #
# --------------------------------------------------------------------------- #


def test_ensure_vault_structure_creates_all_subdirs(tmp_path: Path) -> None:
    root = ensure_vault_structure(tmp_path, "my-novel")
    assert root == project_root(tmp_path, "my-novel")
    for sub in PROJECT_SUBDIRS:
        assert (root / sub).is_dir(), f"missing subdir {sub}"


def test_ensure_vault_structure_is_idempotent(tmp_path: Path) -> None:
    ensure_vault_structure(tmp_path, "n")
    ensure_vault_structure(tmp_path, "n")  # no exception


# --------------------------------------------------------------------------- #
# Chapter file                                                                #
# --------------------------------------------------------------------------- #


def test_write_chapter_creates_file_with_zero_padded_index(tmp_path: Path) -> None:
    ch = _make_chapter(index=47)
    out = write_chapter(tmp_path, "novel-a", ch)
    assert out.name == "0047.md"
    assert out.parent == project_root(tmp_path, "novel-a") / "chapters"
    assert out.exists()


def test_chapter_frontmatter_has_expected_fields(tmp_path: Path) -> None:
    ch = _make_chapter(index=1, title="Chương Mở Đầu")
    out = write_chapter(
        tmp_path,
        "novel-a",
        ch,
        title_zh="第一章 开篇",
        character_names=["Lý Thanh"],
    )
    fm = _parse_frontmatter(out.read_text(encoding="utf-8"))
    assert fm["chapter"] == 1
    assert fm["title"] == {"zh": "第一章 开篇", "vn": "Chương Mở Đầu"}
    assert fm["state"] == "polished"
    assert fm["characters"] == ["[[Lý Thanh]]"]
    assert fm["tokens_used"] == 128
    assert fm["provider"] == "gemini-3.1-flash-lite"


def test_chapter_body_has_source_convert_and_polished_sections(tmp_path: Path) -> None:
    ch = _make_chapter(index=2)
    out = write_chapter(tmp_path, "novel-a", ch)
    text = out.read_text(encoding="utf-8")
    assert "# Chương 2" in text
    assert "> [!source]- Bản gốc" in text
    assert "> 李青走进青云宗。" in text
    assert "> [!info]- Bản convert" in text
    assert "## Bản dịch" in text
    assert "Lý Thanh bước vào" in text


def test_chapter_wraps_character_names_with_wiki_links(tmp_path: Path) -> None:
    ch = _make_chapter(
        index=3,
        polished_text="Lý Thanh gặp Trương Lão tại sơn môn. Lý Thanh cúi chào.",
    )
    out = write_chapter(
        tmp_path,
        "novel-a",
        ch,
        character_names=["Lý Thanh", "Trương Lão", "Wang Wu"],  # last not in text
    )
    text = out.read_text(encoding="utf-8")
    assert "[[Lý Thanh]] gặp [[Trương Lão]] tại sơn môn" in text
    assert "[[Wang Wu]]" not in text
    # Already-bracketed names must not get double-bracketed.
    assert "[[[[" not in text


def test_chapter_skips_missing_sections(tmp_path: Path) -> None:
    ch = _make_chapter(index=4, convert_text=None, polished_text=None, state="raw")
    out = write_chapter(tmp_path, "novel-a", ch)
    text = out.read_text(encoding="utf-8")
    assert "> [!source]- Bản gốc" in text
    assert "> [!info]- Bản convert" not in text
    assert "## Bản dịch" not in text


def test_chapter_rewrite_overwrites(tmp_path: Path) -> None:
    ch1 = _make_chapter(index=5, polished_text="First version.")
    write_chapter(tmp_path, "novel-a", ch1)
    ch2 = _make_chapter(index=5, polished_text="Second version.")
    out = write_chapter(tmp_path, "novel-a", ch2)
    text = out.read_text(encoding="utf-8")
    assert "Second version" in text
    assert "First version" not in text


def test_write_three_chapters(tmp_path: Path) -> None:
    """End-to-end: write 3 fake chapters and verify each file."""
    chapters = [
        _make_chapter(index=i, polished_text=f"Chương số {i} đã polish.") for i in (1, 2, 3)
    ]
    paths = [write_chapter(tmp_path, "novel-a", ch) for ch in chapters]
    assert {p.name for p in paths} == {"0001.md", "0002.md", "0003.md"}
    for ch, p in zip(chapters, paths, strict=True):
        text = p.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        assert fm["chapter"] == ch.index
        assert f"Chương số {ch.index}" in text


# --------------------------------------------------------------------------- #
# Character file                                                              #
# --------------------------------------------------------------------------- #


def test_write_character_creates_file_with_frontmatter(tmp_path: Path) -> None:
    char = Character(
        name="Lý Thanh",
        name_zh="李青",
        aliases=("Tiểu Lý", "Lý sư huynh"),
        role="protagonist",
        description="Đệ tử Thanh Vân Tông, linh căn ngũ hành.",
        first_seen_chapter=1,
    )
    out = write_character(tmp_path, "novel-a", char)
    assert out.parent == project_root(tmp_path, "novel-a") / "characters"
    text = out.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    assert fm["name"] == "Lý Thanh"
    assert fm["name_zh"] == "李青"
    assert fm["aliases"] == ["Tiểu Lý", "Lý sư huynh"]
    assert fm["role"] == "protagonist"
    assert "# Lý Thanh" in text
    assert "Đệ tử Thanh Vân Tông" in text
    assert "```dataview" in text
    assert 'contains(characters, "[[Lý Thanh]]")' in text


def test_character_filename_sanitizes_invalid_chars(tmp_path: Path) -> None:
    char = Character(name="Lý/Thanh:1")
    out = write_character(tmp_path, "novel-a", char)
    assert "/" not in out.name and ":" not in out.name
    assert out.exists()


# --------------------------------------------------------------------------- #
# Dashboard                                                                   #
# --------------------------------------------------------------------------- #


def test_write_dashboard_emits_dataview_blocks(tmp_path: Path) -> None:
    out = write_project_dashboard(tmp_path, "novel-a", project_name="Đại Đạo")
    text = out.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    assert fm == {"project": "novel-a", "type": "dashboard"}
    assert "# 📚 Đại Đạo" in text
    assert text.count("```dataview") == 3
    assert 'FROM "projects/novel-a/chapters"' in text
    assert 'FROM "projects/novel-a/characters"' in text


def test_dashboard_uses_slug_when_no_project_name(tmp_path: Path) -> None:
    out = write_project_dashboard(tmp_path, "my-slug")
    text = out.read_text(encoding="utf-8")
    assert "# 📚 my-slug" in text
