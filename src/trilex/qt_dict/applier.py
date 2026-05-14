"""QuickTranslator dictionary applier — the QT pass.

Chains tiered Aho-Corasick matchers (custom glossary > LuatNhan > Names >
VietPhrase > LacViet > PhienAm) so longer / higher-priority matches win.
Output is raw Hán-Việt: readable but not polished — that is the design intent.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from trilex.qt_dict.automaton import AhoMatcher, load_or_build
from trilex.qt_dict.parser import parse_qt_dict

logger = logging.getLogger(__name__)

DEFAULT_CACHE_SUBDIR: Final[str] = "cache"
NAMES_FILES: Final[tuple[str, ...]] = ("Names.txt", "Names2.txt")
VIETPHRASE_FILE: Final[str] = "Vietphrase.txt"
LACVIET_FILE: Final[str] = "LacViet.txt"
PHIENAM_FILE: Final[str] = "ChinesePhienAmWords.txt"
LUATNHAN_FILE: Final[str] = "LuatNhan.txt"


@dataclass(frozen=True)
class _Segment:
    text: str
    converted: bool


@dataclass(frozen=True)
class Tier:
    name: str
    matcher: AhoMatcher


@dataclass(frozen=True)
class ConvertStats:
    """Per-call timing + per-tier match counts for one QT-pass invocation."""

    input_chars: int
    output_chars: int
    elapsed_seconds: float
    luat_nhan_substitutions: int
    tier_match_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ConvertResult:
    text: str
    stats: ConvertStats


class QTApplier:
    """Apply the QT dictionary chain to ZH text in priority tiers."""

    def __init__(self, dict_dir: Path, cache_dir: Path | None = None) -> None:
        self.dict_dir = Path(dict_dir)
        self.cache_dir = (
            Path(cache_dir) if cache_dir else self.dict_dir.parent / DEFAULT_CACHE_SUBDIR
        )
        self._luat_nhan: list[tuple[re.Pattern[str], str]] = []
        self._tiers: list[Tier] = []
        self._load()

    @property
    def tier_names(self) -> list[str]:
        return [t.name for t in self._tiers]

    def _load(self) -> None:
        ln_path = self.dict_dir / LUATNHAN_FILE
        if ln_path.exists():
            qt = parse_qt_dict(ln_path)
            rules = {k: v[0] for k, v in qt.entries.items()}
            self._luat_nhan = _compile_luat_nhan(rules)
            logger.info("Loaded %d LuatNhan rules", len(self._luat_nhan))

        names_matcher = self._load_merged_aho("names", NAMES_FILES)
        if names_matcher is not None:
            self._tiers.append(Tier(name="names", matcher=names_matcher))

        for fname, label, cleaner in [
            (VIETPHRASE_FILE, "vietphrase", None),
            (LACVIET_FILE, "lacviet", _clean_lacviet_value),
            (PHIENAM_FILE, "phienam", None),
        ]:
            matcher = self._load_single_aho(fname, value_cleaner=cleaner)
            if matcher is not None:
                self._tiers.append(Tier(name=label, matcher=matcher))

        logger.info("QTApplier loaded %d tiers: %s", len(self._tiers), self.tier_names)

    def _load_single_aho(
        self,
        filename: str,
        value_cleaner: Callable[[str], str] | None = None,
    ) -> AhoMatcher | None:
        path = self.dict_dir / filename
        if not path.exists():
            logger.info("Optional dict not found: %s", filename)
            return None
        qt = parse_qt_dict(path)
        if value_cleaner is None:
            entries = {k: v[0] for k, v in qt.entries.items()}
            return load_or_build(entries, path, self.cache_dir)

        # Cleaned variant needs its own cache key so changes to the cleaner
        # invalidate the cache without touching dict files.
        entries = {k: value_cleaner(v[0]) for k, v in qt.entries.items()}
        digest = hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324
        cleaner_tag = value_cleaner.__name__.lstrip("_")
        cache_path = (
            self.cache_dir / f"automaton_{Path(filename).stem.lower()}_{cleaner_tag}_{digest}.pkl"
        )
        if cache_path.exists():
            try:
                return AhoMatcher.load(cache_path)
            except (ValueError, EOFError) as e:
                logger.warning("Cleaned cache load failed (%s); rebuilding", e)
        m = AhoMatcher()
        m.build(entries)
        m.save(cache_path)
        return m

    def _load_merged_aho(self, label: str, filenames: tuple[str, ...]) -> AhoMatcher | None:
        present = [self.dict_dir / f for f in filenames if (self.dict_dir / f).exists()]
        if not present:
            return None

        merged: dict[str, str] = {}
        digest = hashlib.md5()  # noqa: S324
        for path in present:
            qt = parse_qt_dict(path)
            for k, vals in qt.entries.items():
                merged.setdefault(k, vals[0])
            digest.update(path.read_bytes())
        if not merged:
            return None

        cache_path = self.cache_dir / f"automaton_{label}_{digest.hexdigest()}.pkl"
        if cache_path.exists():
            try:
                return AhoMatcher.load(cache_path)
            except (ValueError, EOFError) as e:
                logger.warning("Merged cache load failed (%s); rebuilding", e)

        m = AhoMatcher()
        m.build(merged)
        m.save(cache_path)
        return m

    def convert(
        self,
        text: str,
        custom_glossary: dict[str, str] | None = None,
        verbose: bool = False,
    ) -> str:
        """Run the full QT pass on `text`. Returns raw Hán-Việt output."""
        return self.convert_detail(text, custom_glossary, verbose).text

    def convert_detail(
        self,
        text: str,
        custom_glossary: dict[str, str] | None = None,
        verbose: bool = False,
    ) -> ConvertResult:
        """Run the QT pass and return the output plus per-tier match counts."""
        t0 = time.perf_counter()
        in_chars = len(text)

        if not text:
            return ConvertResult(
                text="",
                stats=ConvertStats(
                    input_chars=0,
                    output_chars=0,
                    elapsed_seconds=0.0,
                    luat_nhan_substitutions=0,
                ),
            )

        ln_subs = 0
        for regex, repl in self._luat_nhan:
            text, n = regex.subn(repl, text)
            ln_subs += n

        tiers = list(self._tiers)
        if custom_glossary:
            glossary_matcher = AhoMatcher()
            glossary_matcher.build(custom_glossary)
            tiers.insert(0, Tier(name="glossary", matcher=glossary_matcher))

        counts: dict[str, int] = {}
        segments: list[_Segment] = [_Segment(text=text, converted=False)]
        for tier in tiers:
            before = sum(1 for s in segments if s.converted)
            segments = _apply_tier(segments, tier, verbose=verbose)
            after = sum(1 for s in segments if s.converted)
            counts[tier.name] = after - before

        out_text = _stitch(segments)
        return ConvertResult(
            text=out_text,
            stats=ConvertStats(
                input_chars=in_chars,
                output_chars=len(out_text),
                elapsed_seconds=time.perf_counter() - t0,
                luat_nhan_substitutions=ln_subs,
                tier_match_counts=counts,
            ),
        )


_LACVIET_HAN_VIET_RE: Final[re.Pattern[str]] = re.compile(r"Hán Việt:\s*(\w+)")
_LACVIET_PINYIN_RE: Final[re.Pattern[str]] = re.compile(r"✚\[[^\]]*\]\s*")


def _clean_lacviet_value(value: str) -> str:
    """Extract a usable Hán-Việt token from a LacViet entry.

    LacViet entries are dictionary-style with pinyin, a `Hán Việt: WORD` block,
    numbered senses, and example sentences. For raw QT pass we only want a short
    Vietnamese token. Strategy:
      - If `Hán Việt: WORD` is present, use WORD (single char readings).
      - Otherwise strip the leading `✚[pinyin]` marker and take the first
        semicolon-delimited sense (compound entries).
    """
    hv = _LACVIET_HAN_VIET_RE.search(value)
    if hv:
        return hv.group(1).strip().lower()

    cleaned = _LACVIET_PINYIN_RE.sub("", value)
    cleaned = cleaned.replace("\\n", " ").replace("\\t", " ").replace("\n", " ").replace("\t", " ")
    first_sense = cleaned.split(";")[0]
    return re.sub(r"\s+", " ", first_sense).strip()


def _compile_luat_nhan(rules: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """Compile `pattern{0}=template{0}` rules to (regex, repl) pairs."""
    placeholder_re = re.compile(r"\{(\d+)\}")
    compiled: list[tuple[re.Pattern[str], str]] = []

    for pattern_text, template in rules.items():
        escaped = re.escape(pattern_text)
        escaped = re.sub(r"\\\{(\d+)\\\}", r"(.+?)", escaped)
        try:
            regex = re.compile(escaped)
        except re.error as e:
            logger.warning("Skipped malformed LuatNhan %r: %s", pattern_text, e)
            continue
        repl = placeholder_re.sub(lambda m: "\\" + str(int(m.group(1)) + 1), template)
        compiled.append((regex, repl))

    compiled.sort(key=lambda pr: -len(pr[0].pattern))
    return compiled


def _apply_tier(segments: list[_Segment], tier: Tier, *, verbose: bool) -> list[_Segment]:
    out: list[_Segment] = []
    for seg in segments:
        if seg.converted:
            out.append(seg)
            continue
        matches = tier.matcher.find_longest_non_overlapping(seg.text)
        if not matches:
            out.append(seg)
            continue
        cursor = 0
        for m in matches:
            if m.start > cursor:
                out.append(_Segment(text=seg.text[cursor : m.start], converted=False))
            out.append(_Segment(text=m.value, converted=True))
            if verbose:
                logger.info("[%s] %r -> %r", tier.name, m.key, m.value)
            cursor = m.end
        if cursor < len(seg.text):
            out.append(_Segment(text=seg.text[cursor:], converted=False))
    return out


def _stitch(segments: list[_Segment]) -> str:
    """Join segments with single spaces; collapse runs of whitespace."""
    parts = [s.text for s in segments if s.text]
    joined = " ".join(parts)
    return re.sub(r"\s+", " ", joined).strip()
