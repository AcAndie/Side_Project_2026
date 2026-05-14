"""Aho-Corasick automaton wrapper for fast multi-pattern matching.

Wraps `pyahocorasick` with build/query API, persistent cache (pickle keyed by
MD5 of source dict file), and stats. The QT pass needs longest-match-wins
semantics — see `find_longest_non_overlapping`.
"""

from __future__ import annotations

import hashlib
import logging
import pickle  # noqa: S403  (used only on caches we wrote ourselves)
import time
from pathlib import Path
from typing import Any, Final

import ahocorasick
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

CACHE_VERSION: Final[int] = 1
CACHE_FILENAME_TEMPLATE: Final[str] = "automaton_{hash}.pkl"


class Match(BaseModel):
    """A single dictionary hit in source text. `end` is exclusive (Pythonic slicing)."""

    model_config = ConfigDict(frozen=True)

    start: int
    end: int
    key: str
    value: str

    def __len__(self) -> int:
        return self.end - self.start


class AhoStats(BaseModel):
    """Build statistics for an automaton."""

    model_config = ConfigDict(frozen=True)

    word_count: int
    node_count: int
    memory_bytes: int
    build_seconds: float

    def format(self) -> str:
        mb = self.memory_bytes / (1024 * 1024)
        return (
            f"words={self.word_count:,}  nodes={self.node_count:,}  "
            f"memory={mb:.2f} MB  build={self.build_seconds:.2f}s"
        )


class AhoMatcher:
    """Aho-Corasick matcher over (key, value) pairs.

    Build once, query many times. Persist via `save()` / `load()` to skip the
    multi-second build on subsequent runs.
    """

    def __init__(self) -> None:
        self._automaton: ahocorasick.Automaton | None = None
        self._stats: AhoStats | None = None

    @property
    def is_built(self) -> bool:
        return self._automaton is not None

    def build(self, entries: dict[str, str]) -> None:
        """Build automaton from `{key: value}` pairs. Empty keys are skipped."""
        t0 = time.perf_counter()
        a: ahocorasick.Automaton = ahocorasick.Automaton()
        for key, value in entries.items():
            if not key:
                continue
            a.add_word(key, (key, value))
        a.make_automaton()
        elapsed = time.perf_counter() - t0

        raw = a.get_stats() if hasattr(a, "get_stats") else {}
        self._automaton = a
        self._stats = AhoStats(
            word_count=int(raw.get("words_count", len(entries))),
            node_count=int(raw.get("nodes_count", -1)),
            memory_bytes=int(raw.get("total_size", -1)),
            build_seconds=elapsed,
        )

    def _ensure_built(self) -> ahocorasick.Automaton:
        if self._automaton is None:
            raise RuntimeError("AhoMatcher not built. Call build() or load() first.")
        return self._automaton

    def find_all(self, text: str) -> list[Match]:
        """Return all matches (including overlaps) in left-to-right order by end."""
        a = self._ensure_built()
        out: list[Match] = []
        for end_idx, (key, value) in a.iter(text):
            start = end_idx - len(key) + 1
            out.append(Match(start=start, end=end_idx + 1, key=key, value=value))
        return out

    def find_longest_non_overlapping(self, text: str) -> list[Match]:
        """Greedy left-to-right scan: at each position, pick the longest match.

        This is the standard QT-pass strategy: longer terms (compounds) win over
        shorter sub-strings, and once a span is consumed the cursor jumps past it.
        """
        longest_at: dict[int, Match] = {}
        for m in self.find_all(text):
            cur = longest_at.get(m.start)
            if cur is None or len(m) > len(cur):
                longest_at[m.start] = m

        result: list[Match] = []
        i = 0
        n = len(text)
        while i < n:
            chosen = longest_at.get(i)
            if chosen is not None:
                result.append(chosen)
                i = chosen.end
            else:
                i += 1
        return result

    def stats(self) -> AhoStats:
        if self._stats is None:
            raise RuntimeError("AhoMatcher not built; no stats available.")
        return self._stats

    def save(self, path: Path) -> None:
        """Pickle automaton + stats to `path`. Creates parent dir if missing."""
        a = self._ensure_built()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "version": CACHE_VERSION,
            "automaton": a,
            "stats": self._stats.model_dump() if self._stats else None,
        }
        with path.open("wb") as fp:
            pickle.dump(payload, fp, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def load(cls, path: Path) -> AhoMatcher:
        """Load a previously saved automaton. Raises ValueError on version mismatch."""
        with path.open("rb") as fp:
            data: dict[str, Any] = pickle.load(fp)  # noqa: S301
        version = data.get("version")
        if version != CACHE_VERSION:
            raise ValueError(f"Cache version mismatch: file={version} expected={CACHE_VERSION}")
        m = cls()
        m._automaton = data["automaton"]
        stats_dict = data.get("stats")
        if stats_dict:
            m._stats = AhoStats.model_validate(stats_dict)
        return m


def cache_path_for(dict_path: Path, cache_dir: Path) -> Path:
    """Build a content-addressed cache file path: `automaton_{md5}.pkl`."""
    digest = hashlib.md5(dict_path.read_bytes()).hexdigest()  # noqa: S324
    return cache_dir / CACHE_FILENAME_TEMPLATE.format(hash=digest)


def load_or_build(
    entries: dict[str, str],
    dict_path: Path,
    cache_dir: Path,
) -> AhoMatcher:
    """Load cached automaton (keyed by MD5 of dict file) if present; else build + save.

    Cache invalidates automatically when the source dict file changes (different MD5
    → different filename). Stale caches accumulate; clean them out periodically.
    """
    cp = cache_path_for(dict_path, cache_dir)
    if cp.exists():
        try:
            logger.info("Loading cached automaton: %s", cp.name)
            return AhoMatcher.load(cp)
        except (ValueError, pickle.UnpicklingError, EOFError) as e:
            logger.warning("Cache load failed (%s); rebuilding", e)

    m = AhoMatcher()
    m.build(entries)
    m.save(cp)
    return m
