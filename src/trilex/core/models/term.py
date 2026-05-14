"""Minimal `Term` model for glossary / name-lock support.

Kept intentionally lean — the persistence-layer (`persistence/repos/glossary_repo.py`)
will eventually back this with SQLAlchemy + UUID + provenance fields. The polish
stage only needs source/target/aliases, so this is what we expose for now.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TermCategory = Literal[
    "character", "skill", "realm", "place", "item", "org", "system_msg", "phrase"
]


class Term(BaseModel):
    """A locked translation pair. Immutable."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    category: TermCategory = "phrase"
    aliases: tuple[str, ...] = ()

    def matches(self, text: str) -> bool:
        """True if `source` or any alias appears in `text` as a substring."""
        if self.source in text:
            return True
        return any(a in text for a in self.aliases)
