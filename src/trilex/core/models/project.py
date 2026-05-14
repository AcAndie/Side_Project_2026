"""Minimal `ProjectConfig` — pipeline-level knobs for translating a chapter.

Full Project model (with UUID, vault path, provenance) lives in the persistence
layer. Here we keep just what `translate_chapter` actually reads, so the
orchestrator can be exercised without spinning up the database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from trilex.core.models.term import Term

Language = Literal["zh", "vn", "en"]


class ProjectConfig(BaseModel):
    """Per-project pipeline knobs. Immutable."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    source_lang: Language
    target_lang: Language
    genre: str = "tu_tien"
    style_pack: str | None = None
    custom_glossary: tuple[Term, ...] = ()
    custom_dict_path: Path | None = None
    dict_dir: Path = Field(default_factory=lambda: Path("data/dictionaries"))
    cache_dir: Path = Field(default_factory=lambda: Path("data/cache"))
    max_tokens: int = 4000

    def style_pack_id(self) -> tuple[str, Language]:
        """Return `(genre, target_lang)` for `get_style_pack()`. Parses `style_pack`
        override of the form `"genre.target_lang"` (e.g. `"tu_tien.vn"`)."""
        if self.style_pack is None:
            return self.genre, self.target_lang
        parts = self.style_pack.split(".")
        if len(parts) != 2:
            raise ValueError(f"style_pack must be 'genre.target_lang', got: {self.style_pack!r}")
        genre, target = parts
        if target not in ("zh", "vn", "en"):
            raise ValueError(f"unknown target_lang in style_pack: {target!r}")
        return genre, target  # type: ignore[return-value]
