"""Scout — lightweight entity / term extractor.

Sends one LLM call with `(ZH chapter, VN translation, existing glossary)` and
asks for **new** proper nouns / terms missing from the glossary. Output is a
strict JSON array; we parse, validate via Pydantic, and dedupe against the
existing glossary before returning `list[NewTerm]`.

The caller decides what to do with results (queue for user review, auto-lock,
etc.). Scout is read-only — it never writes to the DB.

Per CLAUDE.md §13, Scout uses Gemini Flash by default (cheap + fast).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trilex.core.models.term import Term
from trilex.providers.base import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS: Final[int] = 2048

NewTermCategory = Literal[
    "character", "skill", "realm", "place", "item", "org", "sect", "phrase", "other"
]


class NewTerm(BaseModel):
    """One term proposed by Scout. Caller decides accept/reject."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    zh: str = Field(..., min_length=1)
    vn: str = Field(..., min_length=1)
    category: NewTermCategory = "other"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str = ""


_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _strip_fence(text: str) -> str:
    """Pull JSON out of a ```json … ``` (or plain ``` … ```) fence if present."""
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def _parse_json_array(raw: str) -> list[dict[str, object]]:
    cleaned = _strip_fence(raw)
    # Some models leak a leading `JSON:` label.
    cleaned = re.sub(r"^\s*JSON\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Try to recover the first top-level array via a greedy slice.
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                raise ValueError(f"Scout returned invalid JSON: {e}") from e
        else:
            raise ValueError(f"Scout returned invalid JSON: {e}") from e
    if not isinstance(parsed, list):
        raise ValueError(f"Scout JSON must be an array, got {type(parsed).__name__}")
    return parsed


def _build_glossary_block(glossary: Iterable[Term], original: str, *, limit: int = 80) -> str:
    """Slice the glossary down to entries that actually appear in `original`."""
    relevant = [t for t in glossary if t.matches(original)]
    relevant = relevant[:limit]
    if not relevant:
        return "(empty — chương này chưa có term nào locked)"
    return "\n".join(f"  {t.source} -> {t.target}" for t in relevant)


def _build_prompt(original: str, translation: str, glossary: Iterable[Term]) -> tuple[str, str]:
    """Return `(system_prompt, user_prompt)`."""
    system = (
        "You are a literary terminology scout for Chinese-to-Vietnamese translation.\n"
        "Goal: identify NEW proper nouns / cultivation terms / sect names / "
        "place names / skill names / artifact names that appear in the chapter "
        "but are NOT in the existing glossary.\n"
        "Output STRICT JSON only — no preamble, no markdown fence, no commentary."
    )

    user_parts: list[str] = []
    user_parts.append("TASK: Extract NEW terms missing from glossary.")
    user_parts.append("")
    user_parts.append("INSTRUCTIONS:")
    user_parts.append("  1. Compare the Chinese source against the existing glossary.")
    user_parts.append("  2. List ONLY entities that are absent from the glossary.")
    user_parts.append(
        "  3. Provide the Hán-Việt rendering for each (from the translation if present)."
    )
    user_parts.append(
        "  4. Pick category from: character, place, sect, skill, realm, item, org, phrase, other."
    )
    user_parts.append("  5. Confidence is a float 0–1.")
    user_parts.append("  6. Output a JSON array. No surrounding text. No code fence.")
    user_parts.append("")
    user_parts.append("EXISTING GLOSSARY (zh -> vn):")
    user_parts.append(_build_glossary_block(glossary, original))
    user_parts.append("")
    user_parts.append("SOURCE (Chinese):")
    user_parts.append(original)
    user_parts.append("")
    user_parts.append("TRANSLATION (Vietnamese):")
    user_parts.append(translation)
    user_parts.append("")
    user_parts.append("OUTPUT FORMAT (JSON array, no other text):")
    user_parts.append(
        '[{"zh":"<source>","vn":"<target>","category":"character",'
        '"confidence":0.85,"notes":"brief context"}]'
    )

    return system, "\n".join(user_parts)


async def scout_terms(
    *,
    original: str,
    translation: str,
    provider: LLMProvider,
    glossary: Iterable[Term] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[NewTerm]:
    """Return new terms found in `(original, translation)` that are missing
    from `glossary`. Deduped by `zh` source."""
    glossary_list = list(glossary or [])
    system, user = _build_prompt(original, translation, glossary_list)

    response = await provider.complete(prompt=user, system=system, max_tokens=max_tokens)

    try:
        rows = _parse_json_array(response.text)
    except ValueError as e:
        logger.warning("Scout JSON parse failed: %s", e)
        return []

    candidates: list[NewTerm] = []
    seen: set[str] = set()
    existing_sources = {t.source for t in glossary_list}

    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            term = NewTerm.model_validate(row)
        except ValidationError as e:
            logger.debug("Skipping malformed scout row: %s (err=%s)", row, e)
            continue
        if term.zh in existing_sources or term.zh in seen:
            continue
        # Sanity: the proposed source string should at least appear once in the
        # chapter — otherwise the LLM hallucinated it.
        if term.zh not in original:
            logger.debug("Skipping hallucinated term not in source: %r", term.zh)
            continue
        seen.add(term.zh)
        candidates.append(term)

    return candidates
