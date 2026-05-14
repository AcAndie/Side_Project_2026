"""Output adapters — write translated content to user-facing destinations."""

from trilex.output.epub import (
    chapters_for_export,
    export_epub,
    export_vault_zip,
)
from trilex.output.obsidian import (
    ensure_vault_structure,
    project_root,
    write_chapter,
    write_character,
    write_project_dashboard,
)
from trilex.output.plain_text import chapter_to_bbcode, chapter_to_plain_text

__all__ = [
    "chapter_to_bbcode",
    "chapter_to_plain_text",
    "chapters_for_export",
    "ensure_vault_structure",
    "export_epub",
    "export_vault_zip",
    "project_root",
    "write_chapter",
    "write_character",
    "write_project_dashboard",
]
