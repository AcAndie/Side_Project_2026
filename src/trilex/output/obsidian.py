"""Obsidian vault writer.

Lays out each project under `{vault}/projects/{slug}/` with the canonical
folder set from BLUEPRINT §9.2 and writes:
  - `chapters/{idx:04d}.md` — bilingual chapter file with source / convert /
    polished sections inside Obsidian callouts.
  - `characters/{name}.md` — character note with a Dataview block listing the
    chapters they appear in.
  - `_dashboard.md` — Dataview overview of chapters + characters + token stats.

The writer is intentionally side-effect-only and idempotent: rewriting a file
overwrites the previous version. Persistence (the DB) remains the source of
truth — the vault is the *read* surface.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

import yaml

from trilex.core.models.character import Character
from trilex.persistence.models import Chapter

logger = logging.getLogger(__name__)

PROJECT_SUBDIRS: Final[tuple[str, ...]] = (
    "chapters",
    "characters",
    "skills",
    "realms",
    "places",
    "factions",
    "bible",
    "bible/arcs",
)

_INVALID_NAME_RE: Final[re.Pattern[str]] = re.compile(r'[\\/:*?"<>|]')


# --------------------------------------------------------------------------- #
# Folder layout                                                               #
# --------------------------------------------------------------------------- #


def project_root(vault_path: Path, project_slug: str) -> Path:
    return Path(vault_path) / "projects" / project_slug


def ensure_vault_structure(vault_path: Path, project_slug: str) -> Path:
    """Create the per-project folder tree. Returns the project root."""
    root = project_root(vault_path, project_slug)
    for sub in PROJECT_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


# --------------------------------------------------------------------------- #
# Chapter file                                                                #
# --------------------------------------------------------------------------- #


def write_chapter(
    vault_path: Path,
    project_slug: str,
    chapter: Chapter,
    *,
    title_zh: str | None = None,
    character_names: Iterable[str] | None = None,
) -> Path:
    """Write one chapter file. Returns the resulting path."""
    root = ensure_vault_structure(vault_path, project_slug)
    out_path = root / "chapters" / f"{int(chapter.index):04d}.md"

    title_vn = chapter.title or f"Chương {chapter.index}"
    characters_present = _detect_characters(chapter, character_names)

    frontmatter: dict[str, object] = {
        "chapter": int(chapter.index),
        "title": {"zh": title_zh, "vn": title_vn},
        "state": chapter.state,
        "characters": [f"[[{n}]]" for n in characters_present],
        "tokens_used": int(chapter.tokens_used or 0),
        "provider": chapter.provider_used,
        "translated_at": (chapter.translated_at.isoformat() if chapter.translated_at else None),
        "quality_score": chapter.quality_score,
        "warnings": list(chapter.warnings or []),
    }

    parts: list[str] = []
    parts.append("---")
    parts.append(yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).rstrip())
    parts.append("---")
    parts.append("")
    parts.append(f"# Chương {int(chapter.index)} — {title_vn}")
    parts.append("")

    if chapter.source_text:
        parts.extend(_callout("source", "Bản gốc", chapter.source_text))
        parts.append("")
    if chapter.convert_text:
        parts.extend(_callout("info", "Bản convert", chapter.convert_text))
        parts.append("")
    if chapter.polished_text:
        parts.append("## Bản dịch")
        parts.append("")
        parts.append(_link_characters(chapter.polished_text, characters_present))
        parts.append("")

    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def _callout(kind: str, label: str, text: str) -> list[str]:
    """Render an Obsidian callout block. `kind` is the callout type tag."""
    lines = [f"> [!{kind}]- {label}"]
    for line in text.split("\n"):
        lines.append(f"> {line}" if line else ">")
    return lines


def _detect_characters(chapter: Chapter, character_names: Iterable[str] | None) -> list[str]:
    if not character_names:
        return []
    text = chapter.polished_text or chapter.convert_text or chapter.source_text or ""
    return sorted({name for name in character_names if name and name in text})


def _link_characters(text: str, names: list[str]) -> str:
    """Wrap each known character name with `[[name]]`. Longest first to avoid
    nesting (e.g. wrap `Lý Thanh Phong` before `Lý Thanh`)."""
    if not names:
        return text
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(
            r"(?<!\[)" + re.escape(name) + r"(?!\])",
            f"[[{name}]]",
            text,
        )
    return text


# --------------------------------------------------------------------------- #
# Character file                                                              #
# --------------------------------------------------------------------------- #


def write_character(
    vault_path: Path,
    project_slug: str,
    character: Character,
) -> Path:
    """Write one character note. Filename is `{character.name}.md`."""
    root = ensure_vault_structure(vault_path, project_slug)
    safe_name = _safe_filename(character.name)
    out_path = root / "characters" / f"{safe_name}.md"

    frontmatter: dict[str, object] = {
        "name": character.name,
        "name_zh": character.name_zh,
        "name_en": character.name_en,
        "aliases": list(character.aliases),
        "role": character.role,
        "first_seen_chapter": character.first_seen_chapter,
    }

    parts: list[str] = []
    parts.append("---")
    parts.append(yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).rstrip())
    parts.append("---")
    parts.append("")
    parts.append(f"# {character.name}")
    parts.append("")
    if character.description:
        parts.append(character.description.strip())
        parts.append("")
    parts.append("## Xuất hiện trong chương")
    parts.append("```dataview")
    parts.append("LIST")
    parts.append(f'FROM "projects/{project_slug}/chapters"')
    parts.append(f'WHERE contains(characters, "[[{character.name}]]")')
    parts.append("SORT chapter ASC")
    parts.append("```")

    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def _safe_filename(name: str) -> str:
    return _INVALID_NAME_RE.sub("_", name).strip()


# --------------------------------------------------------------------------- #
# Dashboard file                                                              #
# --------------------------------------------------------------------------- #


def write_project_dashboard(
    vault_path: Path,
    project_slug: str,
    project_name: str = "",
) -> Path:
    """Write `_dashboard.md` with Dataview queries over chapters + characters."""
    root = ensure_vault_structure(vault_path, project_slug)
    out_path = root / "_dashboard.md"

    title = project_name or project_slug
    chapters_folder = f"projects/{project_slug}/chapters"
    characters_folder = f"projects/{project_slug}/characters"

    parts: list[str] = []
    parts.append("---")
    parts.append(
        yaml.safe_dump(
            {"project": project_slug, "type": "dashboard"},
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
    )
    parts.append("---")
    parts.append("")
    parts.append(f"# 📚 {title}")
    parts.append("")
    parts.append("## Chương")
    parts.append("```dataview")
    parts.append('TABLE WITHOUT ID file.link AS "Chương", state, tokens_used, provider')
    parts.append(f'FROM "{chapters_folder}"')
    parts.append("SORT chapter ASC")
    parts.append("```")
    parts.append("")
    parts.append("## Nhân vật")
    parts.append("```dataview")
    parts.append("LIST")
    parts.append(f'FROM "{characters_folder}"')
    parts.append("SORT file.name ASC")
    parts.append("```")
    parts.append("")
    parts.append("## Thống kê theo trạng thái")
    parts.append("```dataview")
    parts.append("TABLE WITHOUT ID")
    parts.append('  rows.state[0] AS "Trạng thái",')
    parts.append('  length(rows) AS "Số chương",')
    parts.append('  sum(rows.tokens_used) AS "Tokens"')
    parts.append(f'FROM "{chapters_folder}"')
    parts.append("GROUP BY state")
    parts.append("```")

    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path
