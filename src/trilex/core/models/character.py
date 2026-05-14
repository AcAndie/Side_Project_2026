"""Minimal `Character` model — input to the vault character-file writer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Character(BaseModel):
    """Character metadata for an Obsidian vault note. Immutable."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(..., min_length=1)
    name_zh: str | None = None
    name_en: str | None = None
    aliases: tuple[str, ...] = ()
    role: str = ""
    description: str = ""
    first_seen_chapter: int | None = None
