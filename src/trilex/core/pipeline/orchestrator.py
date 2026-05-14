"""Chapter-level pipeline orchestrator.

Wires the stages (preprocess → QT pass → polish → postprocess) into a single
async entrypoint `translate_chapter`. Per BLUEPRINT §5, this layer is pure:
it never persists anything. Persistence (vault writer, SQLite repo) wraps the
orchestrator from outside and consumes a `ChapterResult`.

Modes:
  - `convert`        → QT pass only, no LLM (free, instant)
  - `polish`         → QT pass + LLM polish (default)
  - `side_by_side`   → same as polish but `convert_text` is preserved so the
                       caller can render a 3-column view

Skip rules:
  - QT pass is skipped if `source_lang != "zh"` (the QT engine only operates
    on Chinese source).
  - Polish is skipped if `mode == "convert"`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from trilex.core.models.project import ProjectConfig
from trilex.core.pipeline.stages.polish import polish
from trilex.core.pipeline.stages.postprocess import postprocess
from trilex.core.pipeline.stages.preprocess import preprocess
from trilex.core.style_pack import StylePack, get_style_pack
from trilex.providers.base import LLMProvider, ProviderError
from trilex.qt_dict.applier import QTApplier

logger = logging.getLogger(__name__)

Mode = Literal["convert", "polish", "side_by_side"]
VALID_MODES: tuple[Mode, ...] = ("convert", "polish", "side_by_side")

ChapterState = Literal[
    "raw",
    "preprocessed",
    "converted",
    "polished",
    "postprocessed",
    "failed",
]


@dataclass(frozen=True)
class StageStats:
    name: str
    elapsed_ms: float
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChapterResult:
    """All artifacts + diagnostics from one `translate_chapter` call."""

    source_text: str
    preprocessed_text: str
    convert_text: str | None
    polished_text: str | None
    final_text: str

    mode: Mode
    state: ChapterState
    warnings: list[str]
    stage_stats: list[StageStats]

    tokens_used: int
    total_elapsed_ms: float
    model: str | None


async def translate_chapter(
    source_text: str,
    project_config: ProjectConfig,
    *,
    mode: Mode = "polish",
    provider: LLMProvider | None = None,
    applier: QTApplier | None = None,
    style_pack: StylePack | None = None,
    fallback_to_convert: bool = True,
) -> ChapterResult:
    """Run the pipeline for one chapter and return a `ChapterResult`.

    ``fallback_to_convert`` (default True): if the LLM polish stage raises
    ``ProviderError`` (quota, network, safety, timeout), the pipeline degrades
    to ``mode="convert"`` and returns the QT-only output with a
    ``polish.fallback_to_convert:<error>`` warning. Set to ``False`` to keep
    the old ``state="failed"`` behaviour.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if mode != "convert" and provider is None:
        raise ValueError("provider is required when mode != 'convert'")

    t_start = time.perf_counter()
    warnings: list[str] = []
    stats: list[StageStats] = []
    tokens_used = 0
    model: str | None = None

    # ─── Stage 1: Preprocess ───────────────────────────────────────────────
    t0 = time.perf_counter()
    preprocessed, pre_warn = preprocess(source_text)
    stats.append(StageStats("preprocess", _ms(t0)))
    warnings.extend(f"preprocess.{w}" for w in pre_warn)

    if not preprocessed:
        return _failed(
            source_text=source_text,
            preprocessed=preprocessed,
            mode=mode,
            warnings=warnings,
            stats=stats,
            t_start=t_start,
        )

    # ─── Stage 2: QT pass ──────────────────────────────────────────────────
    # QT dict only converts ZH → Hán-Việt readable form. Pointless for ZH→EN.
    convert_text: str | None = None
    if project_config.source_lang == "zh" and project_config.target_lang == "vn":
        t0 = time.perf_counter()
        if applier is None:
            applier = QTApplier(project_config.dict_dir, cache_dir=project_config.cache_dir)
        custom_glossary = {t.source: t.target for t in project_config.custom_glossary}
        result = applier.convert_detail(
            preprocessed,
            custom_glossary=custom_glossary or None,
        )
        convert_text = result.text
        stats.append(
            StageStats(
                "qt_pass",
                _ms(t0),
                extra={
                    "tier_match_counts": dict(result.stats.tier_match_counts),
                    "luat_nhan_substitutions": result.stats.luat_nhan_substitutions,
                },
            )
        )
    else:
        if project_config.source_lang != "zh":
            warnings.append("qt_pass.skipped:source_not_zh")
        else:
            warnings.append("qt_pass.skipped:target_not_vn")

    # If convert-only, post-process and return.
    if mode == "convert":
        bulk_for_post = convert_text if convert_text is not None else preprocessed
        final, post_warn = _run_postprocess(bulk_for_post, stats, warnings)
        return ChapterResult(
            source_text=source_text,
            preprocessed_text=preprocessed,
            convert_text=convert_text,
            polished_text=None,
            final_text=final,
            mode=mode,
            state="postprocessed",
            warnings=warnings,
            stage_stats=stats,
            tokens_used=0,
            total_elapsed_ms=_ms(t_start),
            model=None,
        )

    # ─── Stage 3: Polish (LLM) ─────────────────────────────────────────────
    if style_pack is None:
        genre, target_lang = project_config.style_pack_id()
        style_pack = get_style_pack(genre, target_lang)

    converted_for_llm = convert_text if convert_text is not None else preprocessed

    is_full_translation = convert_text is None
    t0 = time.perf_counter()
    try:
        assert provider is not None
        polish_result = await polish(
            original=preprocessed,
            converted=converted_for_llm,
            style_pack=style_pack,
            provider=provider,
            glossary=list(project_config.custom_glossary),
            max_tokens=project_config.max_tokens,
            source_lang=project_config.source_lang,
            is_full_translation=is_full_translation,
        )
    except ProviderError as e:
        warnings.append(f"polish.provider_error:{type(e).__name__}:{e}")
        stats.append(StageStats("polish", _ms(t0), extra={"status": "failed"}))
        if fallback_to_convert:
            # Graceful degradation: skip LLM, return convert-mode output. Caller
            # can still see the original failure in `warnings`.
            warnings.append(f"polish.fallback_to_convert:{type(e).__name__}")
            logger.warning(
                "polish failed (%s), falling back to convert-only output",
                type(e).__name__,
            )
            bulk_for_post = convert_text if convert_text is not None else preprocessed
            final, _post_warn = _run_postprocess(bulk_for_post, stats, warnings)
            return ChapterResult(
                source_text=source_text,
                preprocessed_text=preprocessed,
                convert_text=convert_text,
                polished_text=None,
                final_text=final,
                mode=mode,
                state="postprocessed",
                warnings=warnings,
                stage_stats=stats,
                tokens_used=0,
                total_elapsed_ms=_ms(t_start),
                model=None,
            )
        return _failed(
            source_text=source_text,
            preprocessed=preprocessed,
            mode=mode,
            warnings=warnings,
            stats=stats,
            t_start=t_start,
            convert_text=convert_text,
        )

    stats.append(
        StageStats(
            "polish",
            _ms(t0),
            extra={
                "tokens": polish_result.tokens_used,
                "latency_ms": polish_result.latency_ms,
                "model": polish_result.model,
            },
        )
    )
    warnings.extend(f"polish.{w}" for w in polish_result.warnings)
    tokens_used = polish_result.tokens_used
    model = polish_result.model

    # ─── Stage 4: Postprocess ──────────────────────────────────────────────
    final, _ = _run_postprocess(polish_result.text, stats, warnings)

    return ChapterResult(
        source_text=source_text,
        preprocessed_text=preprocessed,
        convert_text=convert_text,
        polished_text=polish_result.text,
        final_text=final,
        mode=mode,
        state="postprocessed",
        warnings=warnings,
        stage_stats=stats,
        tokens_used=tokens_used,
        total_elapsed_ms=_ms(t_start),
        model=model,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def _run_postprocess(
    text: str, stats: list[StageStats], warnings: list[str]
) -> tuple[str, list[str]]:
    t0 = time.perf_counter()
    out, post_warn = postprocess(text)
    stats.append(StageStats("postprocess", _ms(t0)))
    warnings.extend(f"postprocess.{w}" for w in post_warn)
    return out, post_warn


def _failed(
    *,
    source_text: str,
    preprocessed: str,
    mode: Mode,
    warnings: list[str],
    stats: list[StageStats],
    t_start: float,
    convert_text: str | None = None,
) -> ChapterResult:
    return ChapterResult(
        source_text=source_text,
        preprocessed_text=preprocessed,
        convert_text=convert_text,
        polished_text=None,
        final_text="",
        mode=mode,
        state="failed",
        warnings=warnings,
        stage_stats=stats,
        tokens_used=0,
        total_elapsed_ms=_ms(t_start),
        model=None,
    )
