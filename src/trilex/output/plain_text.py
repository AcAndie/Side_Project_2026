"""Plain-text + BBCode formatters for chapter export.

`chapter_to_plain_text` strips ALL formatting so the result is paste-safe into
notepad, sstruyen, tangthuvien, wikidich text fields. `chapter_to_bbcode`
wraps the same content in standard forum BBCode for posting to phpBB-style
boards. Both are pure functions over `Chapter` rows.
"""

from __future__ import annotations

from trilex.persistence.models import Chapter


def chapter_to_plain_text(chapter: Chapter) -> str:
    """Return the polished text (or convert text fallback) with no markup.

    Used for "Copy" buttons / .txt downloads. Output is the chapter body
    only — no title header, no callouts, no frontmatter — so it pastes
    cleanly into web text fields that strip formatting.
    """
    body = chapter.polished_text or chapter.convert_text or chapter.source_text or ""
    title = chapter.title
    if title:
        return f"{title}\n\n{body.strip()}"
    return body.strip()


def chapter_to_bbcode(
    chapter: Chapter,
    *,
    include_source: bool = False,
    include_convert: bool = False,
) -> str:
    """Return forum-ready BBCode. By default only the polished text is wrapped.

    Use the include flags to add the ZH source and / or QT convert in collapsed
    `[spoiler]` blocks above the polished body — useful for QC threads but
    noisy for plain posts.
    """
    parts: list[str] = []

    header = f"Chương {int(chapter.index)}"
    if chapter.title:
        header += f" — {chapter.title}"
    parts.append(f"[b][size=14]{header}[/size][/b]")
    parts.append("")

    if include_source and chapter.source_text:
        parts.append("[spoiler=Bản gốc]")
        parts.append(chapter.source_text.strip())
        parts.append("[/spoiler]")
        parts.append("")

    if include_convert and chapter.convert_text:
        parts.append("[spoiler=Bản convert]")
        parts.append(chapter.convert_text.strip())
        parts.append("[/spoiler]")
        parts.append("")

    body = chapter.polished_text or chapter.convert_text or chapter.source_text or ""
    parts.append(body.strip())
    return "\n".join(parts)
