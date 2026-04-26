"""
src/littrans/ui/pages/bible_page.py — Tab Bible (Phase 3 rebuild).

Backing implementation lives in `littrans.ui.bible_ui` (sub-tabs Overview /
Database / WorldBuilding / Main Lore / Consistency). Export sub-tab dropped
in Phase 3 — bible export now lives under tab Export (export_page.py).

Also exposes `render_bible_export` which the Export page mounts.
"""
from __future__ import annotations

from typing import Any

# Re-export — Bible UI lives in bible_ui.py (will eventually fold in here once
# the file is no longer imported elsewhere).
from littrans.ui.bible_ui import (
    render_bible_tab     as render_bible,
    render_bible_export,
)

__all__ = ["render_bible", "render_bible_export"]
