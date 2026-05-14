"""Polish stage — turn a QT-converted draft into smooth target-language text.

The polish stage assumes the *convert* layer has already replaced names, realm
terms, and compound vocabulary with their Hán-Việt equivalents. The LLM's job
is purely to fix word order, smooth grammar, and pick natural connectives —
NOT to translate from scratch. This keeps token usage low and prevents the
classic AI failure modes (name drift, realm hallucination, glossary leak).

`polish()` returns a `PolishResult` with `text`, `tokens_used`, `warnings`.
Persistence is the caller's responsibility (per BLUEPRINT §5 stage 8).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Final

from trilex.core.models.term import Term
from trilex.core.style_pack import StylePack
from trilex.providers.base import DEFAULT_MAX_TOKENS, LLMProvider

logger = logging.getLogger(__name__)

LENGTH_MIN_RATIO: Final[float] = 0.8
LENGTH_MAX_RATIO: Final[float] = 1.5
FEW_SHOT_LIMIT: Final[int] = 3
BANNED_HINT_LIMIT: Final[int] = 12

_CJK_RE: Final[re.Pattern[str]] = re.compile(r"[㐀-䶿一-鿿]")
_MARKDOWN_NOISE_RE: Final[re.Pattern[str]] = re.compile(r"```|<\s*\w+\s*>")
_AI_PREAMBLE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:Đây là bản dịch[^\n]*\n|Bản dịch[^\n]*\n|Sau đây là[^\n]*\n|"
    r"Here is[^\n]*\n|Below is[^\n]*\n)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PolishResult:
    """One polish call result. Immutable."""

    text: str
    tokens_used: int
    model: str
    latency_ms: float
    warnings: list[str] = field(default_factory=list)


async def polish(
    *,
    original: str,
    converted: str,
    style_pack: StylePack,
    provider: LLMProvider,
    glossary: list[Term] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    source_lang: str = "zh",
    is_full_translation: bool = False,
) -> PolishResult:
    """Polish `converted` against `original`, steered by `style_pack` + `glossary`.

    When `is_full_translation=True` (e.g. EN→VN), the prompt asks the LLM to
    *translate* from scratch rather than polish a QT draft — `converted` may
    equal `original` in that case.
    """
    glossary = list(glossary or [])
    glossary_slice = [t for t in glossary if t.matches(original)]

    system_prompt = _build_system_prompt(style_pack, is_full_translation)
    user_prompt = _build_user_prompt(
        original,
        converted,
        style_pack,
        glossary_slice,
        source_lang=source_lang,
        is_full_translation=is_full_translation,
    )

    response = await provider.complete(
        prompt=user_prompt,
        system=system_prompt,
        max_tokens=max_tokens,
    )

    text = _strip_preamble(response.text.strip())
    warnings = _validate(text, converted, glossary_slice, style_pack)

    return PolishResult(
        text=text,
        tokens_used=response.tokens_used,
        model=response.model,
        latency_ms=response.latency_ms,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# Prompt construction                                                         #
# --------------------------------------------------------------------------- #


_GENRE_LABEL: Final[dict[str, str]] = {
    "tu_tien": "tiểu thuyết tu tiên Trung Quốc",
    "litrpg": "tiểu thuyết LitRPG / GameLit",
    "vu_su": "tiểu thuyết võ sư",
    "hien_dai": "tiểu thuyết hiện đại",
    "other": "tiểu thuyết online",
}

_TARGET_LANG_LABEL: Final[dict[str, str]] = {
    "vn": "tiếng Việt",
    "en": "English",
    "zh": "中文",
}

_SOURCE_LANG_LABEL: Final[dict[str, str]] = {
    "zh": "tiếng Trung",
    "en": "tiếng Anh",
    "vn": "tiếng Việt",
}


def _build_system_prompt(pack: StylePack, is_full_translation: bool) -> str:
    tone = pack.tone_directives
    genre_label = _GENRE_LABEL.get(pack.genre, pack.genre)
    target_label = _TARGET_LANG_LABEL.get(pack.target_lang, pack.target_lang)

    role = f"Bạn là một dịch giả {genre_label} chuyên nghiệp."
    lines = [
        role,
        f"Genre: {pack.genre}. Target: {target_label}.",
        f"Register: {tone.voice_register or 'tự nhiên, phù hợp genre'}.",
        f"Narrator voice: {tone.narrator_voice or 'ngôi thứ ba'}.",
    ]
    if tone.dialogue_style:
        lines.append(f"Dialogue style: {tone.dialogue_style.strip()}")
    if pack.vocabulary_rules.prefer_han_viet:
        lines.append(
            "LUÔN ưu tiên Hán-Việt cho thuật ngữ tu luyện, tên riêng, cảnh giới, pháp bảo."
        )
    if pack.genre == "litrpg":
        lines.append(
            "GIỮ NGUYÊN mọi token format game: [Skill], [Stat], <System>, +EXP, HP/MP, "
            "tên item/skill (Fireball KHÔNG dịch thành 'Cầu lửa')."
        )
    lines.append(
        "KHÔNG thêm preamble (kiểu 'Đây là bản dịch...'), KHÔNG giải thích, "
        f"KHÔNG markdown — chỉ output bản dịch thuần {target_label}."
    )
    return "\n".join(lines)


def _build_user_prompt(
    original: str,
    converted: str,
    pack: StylePack,
    glossary: list[Term],
    *,
    source_lang: str,
    is_full_translation: bool,
) -> str:
    parts: list[str] = []

    target_lang = pack.target_lang
    original_lc = original.lower()
    if pack.realm_ladder:
        parts.append("CẢNH GIỚI (giữ chính xác, viết hoa):")
        for r in pack.realm_ladder:
            tgt = r.target(target_lang) or r.vn
            if tgt:
                parts.append(f"  {r.zh} -> {tgt}")

    used_honorifics = [
        h for h in pack.honorifics if (src := h.source(source_lang)) and src.lower() in original_lc
    ]
    if used_honorifics:
        parts.append("\nXƯNG HÔ XUẤT HIỆN TRONG CHƯƠNG:")
        for h in used_honorifics:
            tgt = h.target(target_lang) or h.vn
            if tgt:
                parts.append(f"  {h.source(source_lang)} -> {tgt}")

    vocab_slice = [
        v
        for v in pack.vocabulary_rules.examples
        if (vsrc := v.source(source_lang)) and vsrc.lower() in original_lc
    ]
    if vocab_slice:
        parts.append("\nTỪ VỰNG ÁP DỤNG:")
        for v in vocab_slice:
            src = v.source(source_lang)
            tgt = v.target(target_lang) or v.vn
            if not tgt:
                continue
            line = f"  {src} -> {tgt}"
            if v.avoid:
                line += f"  (DO NOT use: '{v.avoid}')"
            parts.append(line)

    if pack.genre == "litrpg" and getattr(pack, "game_tokens_preserved", None):
        tokens = pack.game_tokens_preserved  # type: ignore[attr-defined]
        if isinstance(tokens, list) and tokens:
            parts.append("\nTOKEN GAME PHẢI GIỮ NGUYÊN KÝ TỰ:")
            for t in tokens[:20]:
                parts.append(f"  {t}")

    if glossary:
        parts.append("\nGLOSSARY BẮT BUỘC (PHẢI dùng đúng nguyên văn, không sáng tác):")
        for t in glossary:
            parts.append(f"  {t.source} -> {t.target}")

    if pack.banned_phrases:
        parts.append("\nKHÔNG ĐƯỢC dùng các cụm sau:")
        for b in pack.banned_phrases[:BANNED_HINT_LIMIT]:
            parts.append(f"  - {b}")

    if pack.few_shot_examples:
        parts.append("\nVÍ DỤ DỊCH MẪU (học theo style, không copy):")
        for ex in pack.few_shot_examples[:FEW_SHOT_LIMIT]:
            parts.append(f"\n[NGUỒN]\n{ex.source.strip()}")
            parts.append(f"[DỊCH]\n{ex.target.strip()}")

    src_label = _SOURCE_LANG_LABEL.get(source_lang, source_lang)
    tgt_label = _TARGET_LANG_LABEL.get(pack.target_lang, pack.target_lang)

    if is_full_translation:
        parts.extend(
            [
                "\n=== NHIỆM VỤ ===",
                f"Dịch văn bản {src_label} dưới đây sang {tgt_label} đầy đủ, mượt mà, tự nhiên.",
                "Yêu cầu:",
                "  1. GIỮ NGUYÊN mọi token format đặc biệt: [Skill], [Stat], <System>,"
                " HP/MP, +EXP, v.v.",
                "  2. GIỮ NGUYÊN tên item/skill proper noun (Fireball, Ice Spike)"
                " — KHÔNG dịch nghĩa",
                "  3. PHẢI dùng glossary đúng nguyên văn",
                "  4. Đại từ nhân vật nhất quán; dùng đại từ phù hợp register",
                "  5. KHÔNG thêm preamble, KHÔNG giải thích — chỉ output bản dịch",
                "",
                f"[NGUYÊN BẢN {src_label.upper()}]",
                original,
                "",
                f"[BẢN DỊCH {tgt_label.upper()} — output của bạn]",
            ]
        )
    else:
        parts.extend(
            [
                "\n=== NHIỆM VỤ ===",
                f"Polish bản convert thô bên dưới thành {tgt_label} mượt mà, tự nhiên.",
                "Bản convert đã apply từ điển QT — tên riêng & cảnh giới đã đúng Hán-Việt.",
                "Việc của bạn:",
                "  1. Sắp xếp lại trật tự từ theo ngữ pháp đích",
                "  2. Sửa giới từ, liên từ, hư từ cho mượt",
                "  3. GIỮ NGUYÊN tên riêng, cảnh giới, thuật ngữ",
                "  4. Tham chiếu bản gốc cho sắc thái khi convert thiếu",
                "  5. Giữ đại từ nhân vật nhất quán",
                "",
                f"[NGUYÊN BẢN {src_label.upper()} — tham chiếu sắc thái]",
                original,
                "",
                "[BẢN CONVERT QT — bulk text cần polish]",
                converted,
                "",
                "[BẢN DỊCH MƯỢT — output của bạn, KHÔNG kèm preamble]",
            ]
        )

    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Validation                                                                  #
# --------------------------------------------------------------------------- #


def _strip_preamble(text: str) -> str:
    return _AI_PREAMBLE_RE.sub("", text).strip()


def _validate(
    text: str,
    converted: str,
    glossary: list[Term],
    pack: StylePack,
) -> list[str]:
    warnings: list[str] = []

    if not text:
        warnings.append("empty_output")
        return warnings

    if _MARKDOWN_NOISE_RE.search(text):
        warnings.append("markdown_or_html_garbage")

    residual = _CJK_RE.findall(text)
    if residual:
        warnings.append(f"residual_cjk:{len(residual)}")

    for term in glossary:
        if term.target not in text:
            warnings.append(f"name_violation:{term.source}->{term.target}")

    text_lower = text.lower()
    banned_hits = [b for b in pack.banned_phrases if b.lower() in text_lower]
    if banned_hits:
        warnings.append(f"banned_phrases:{len(banned_hits)}")

    forbidden_hits = [b for b in pack.quality_checks.forbidden_in_output if b.lower() in text_lower]
    if forbidden_hits:
        warnings.append(f"forbidden_in_output:{len(forbidden_hits)}")

    if converted:
        ratio = len(text) / len(converted)
        if ratio < LENGTH_MIN_RATIO:
            warnings.append(f"too_short:ratio={ratio:.2f}")
        elif ratio > LENGTH_MAX_RATIO:
            warnings.append(f"too_long:ratio={ratio:.2f}")

    return warnings
