"""Style pack loader + Pydantic schema.

A style pack is a YAML file that captures the *taste* of one (genre × target
language) pair: vocabulary preferences, realm ladders, honorifics, banned
phrases, and few-shot examples. It is the main knob translators have for
steering the LLM polish stage without retraining models.

Schema is intentionally permissive (extras are ignored) so individual packs
can carry pack-specific keys without breaking the loader.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Language = Literal["zh", "vn", "en"]
Genre = Literal["tu_tien", "litrpg", "vu_su", "hien_dai", "other", "general"]

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
DEFAULT_PACKS_DIR: Final[Path] = PROJECT_ROOT / "packs" / "style"


class StylePackError(ValueError):
    """Raised when a style pack fails to load or validate."""


class _PermissiveModel(BaseModel):
    """Allow unknown keys so packs can evolve without breaking older code."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class VocabExample(_PermissiveModel):
    zh: str | None = None
    en: str | None = None
    vn: str | None = None
    avoid: str | None = None

    def source(self, lang: str) -> str | None:
        return getattr(self, lang, None)

    def target(self, lang: str) -> str | None:
        return getattr(self, lang, None)


class VocabularyRules(_PermissiveModel):
    prefer_han_viet: bool = True
    examples: list[VocabExample] = Field(default_factory=list)


class RealmTier(_PermissiveModel):
    zh: str
    vn: str | None = None
    en: str | None = None
    rank: int | None = None
    notes: str | None = None

    def target(self, lang: str) -> str | None:
        return getattr(self, lang, None)


class StageModifier(_PermissiveModel):
    zh: str
    vn: str | None = None
    en: str | None = None

    def target(self, lang: str) -> str | None:
        return getattr(self, lang, None)


class Honorific(_PermissiveModel):
    zh: str | None = None
    en: str | None = None
    vn: str | None = None
    use_when: str | None = None

    def source(self, lang: str) -> str | None:
        return getattr(self, lang, None)

    def target(self, lang: str) -> str | None:
        return getattr(self, lang, None)


class PreferredPhrase(_PermissiveModel):
    preferred: str
    avoid: str | None = None


class FewShotExample(_PermissiveModel):
    id: str | None = None
    source: str
    target: str
    notes: str | None = None


class PunctuationDirective(_PermissiveModel):
    use_em_dash: bool = True
    use_ellipsis: bool = True
    avoid_exclamation_overuse: bool = True


class ToneDirectives(_PermissiveModel):
    # Field name avoids shadowing `BaseModel.register` (pydantic warning).
    voice_register: str | None = Field(default=None, alias="register")
    narrator_voice: str | None = None
    dialogue_style: str | None = None
    pacing: str | None = None
    punctuation: PunctuationDirective = Field(default_factory=PunctuationDirective)

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class QualityChecks(_PermissiveModel):
    required_keep: list[str] = Field(default_factory=list)
    forbidden_in_output: list[str] = Field(default_factory=list)
    max_translationese_ratio: float = 0.05


class StylePack(_PermissiveModel):
    """Validated style pack — the unit a polish prompt is built from."""

    name: str
    description: str | None = None
    version: int = 1
    source_langs: list[Language]
    target_lang: Language
    genre: Genre = "other"

    vocabulary_rules: VocabularyRules = Field(default_factory=VocabularyRules)
    realm_ladder: list[RealmTier] = Field(default_factory=list)
    stage_modifiers: list[StageModifier] = Field(default_factory=list)
    honorifics: list[Honorific] = Field(default_factory=list)
    sect_suffixes: list[str] = Field(default_factory=list)
    place_suffixes: list[str] = Field(default_factory=list)
    banned_phrases: list[str] = Field(default_factory=list)
    preferred_phrases: list[PreferredPhrase] = Field(default_factory=list)
    tone_directives: ToneDirectives = Field(default_factory=ToneDirectives)
    few_shot_examples: list[FewShotExample] = Field(default_factory=list)
    quality_checks: QualityChecks = Field(default_factory=QualityChecks)

    @model_validator(mode="after")
    def _validate_consistency(self) -> StylePack:
        if not self.source_langs:
            raise ValueError("source_langs must not be empty")
        if self.target_lang in self.source_langs:
            raise ValueError(f"target_lang {self.target_lang!r} cannot also be in source_langs")
        if self.realm_ladder:
            ranks = [r.rank for r in self.realm_ladder if r.rank is not None]
            if ranks != sorted(ranks):
                raise ValueError("realm_ladder ranks must be monotonically increasing")
        return self


def load_style_pack(path: Path) -> StylePack:
    """Parse + validate one YAML pack. Raises `StylePackError` on failure."""
    if not path.exists():
        raise StylePackError(f"Style pack not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise StylePackError(f"YAML parse error in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise StylePackError(f"Style pack must be a mapping, got {type(raw).__name__}")
    try:
        return StylePack.model_validate(raw)
    except Exception as e:
        raise StylePackError(f"Invalid style pack {path}: {e}") from e


def pack_filename(genre: str, target_lang: Language) -> str:
    return f"{genre}.{target_lang}.yaml"


@lru_cache(maxsize=32)
def get_style_pack(
    genre: str,
    target_lang: Language,
    packs_dir: Path = DEFAULT_PACKS_DIR,
) -> StylePack:
    """Locate and load a pack by `(genre, target_lang)`. Cached per process."""
    return load_style_pack(packs_dir / pack_filename(genre, target_lang))
