"""Demo: build (or load cached) Aho-Corasick automaton from Vietphrase.txt
and run a sample query. Cold run takes ~10-30s; warm run reads pickle cache.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from trilex.qt_dict import (
    AhoMatcher,
    cache_path_for,
    load_or_build,
    parse_qt_dict,
)

ROOT = Path(__file__).resolve().parents[1]
DICT_FILE = ROOT / "data" / "dictionaries" / "Vietphrase.txt"
CACHE_DIR = ROOT / "data" / "cache"

# Synthetic xianxia paragraph (~500 hanzi) to demonstrate matching
SAMPLE_TEXT = (
    "林天望着面前的金丹大圆满老者，心中涌起一股难以言喻的敬畏。这位前辈乃是青云"
    "宗的太上长老，曾经在三百年前一战成名，斩杀过元婴期的妖兽。他盘膝而坐，开始"
    "运转九转玄功，体内灵气如同江河奔涌，丹田中的金丹散发出耀眼的光芒。突然，一"
    "道天雷从九天之上劈下，林天的瞳孔骤然收缩，他知道，劫难来了。这是渡劫期修士"
    "才会遇到的天劫，但是他不过区区金丹期。难道是金丹品质太高，引发了不该来的天"
    "劫？他咬紧牙关，运转护身罡气，准备硬抗这一击。雷霆轰鸣，紫色的雷电在虚空中"
    "盘旋，仿佛要将整片天地撕裂。林天怒吼一声，体内九条真龙虚影盘旋而起，护住他"
    "的周身。他要在这一劫中蜕变，从金丹期一跃而入元婴境界！"
)


def _flatten(qt_path: Path) -> tuple[dict[str, str], int]:
    """Parse QT dict and pick first meaning per key. Returns (entries, raw_count)."""
    qt = parse_qt_dict(qt_path)
    flat = {k: v[0] for k, v in qt.entries.items()}
    return flat, qt.meta.count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    cache_file = cache_path_for(DICT_FILE, CACHE_DIR)
    cache_existed_before = cache_file.exists()
    print(f"Cache file: {cache_file.name}")
    print(f"Cache existed before this run: {cache_existed_before}")
    print()

    # If cache exists, load directly without parsing the dict (fast path).
    # If not, parse + build + save.
    t0 = time.perf_counter()
    if cache_existed_before:
        matcher = AhoMatcher.load(cache_file)
    else:
        print("Parsing Vietphrase.txt ...")
        entries, raw_count = _flatten(DICT_FILE)
        print(f"  parsed {raw_count:,} entries")
        print("Building automaton (this takes a while) ...")
        matcher = load_or_build(entries, DICT_FILE, CACHE_DIR)
    total_seconds = time.perf_counter() - t0

    s = matcher.stats()
    print()
    print("=== Automaton stats ===")
    print(f"  {s.format()}")
    print(f"  Total load+build time this run: {total_seconds:.2f}s")
    print()

    print(f"=== Query sample ({len(SAMPLE_TEXT)} hanzi) ===")
    t0 = time.perf_counter()
    matches = matcher.find_longest_non_overlapping(SAMPLE_TEXT)
    query_seconds = time.perf_counter() - t0
    print(f"  query_time={query_seconds * 1000:.2f} ms")
    print(f"  matches={len(matches)}")
    print()

    print("=== First 20 matches ===")
    for m in matches[:20]:
        print(f"  [{m.start:3d}:{m.end:3d}]  {m.key!r:12s} -> {m.value!r}")
    print()

    if len(matches) > 0:
        coverage = sum(len(m) for m in matches)
        pct = coverage / len(SAMPLE_TEXT) * 100
        print(f"Coverage: {coverage}/{len(SAMPLE_TEXT)} chars ({pct:.1f}%)")

    if not cache_existed_before:
        logger.info("Cache file written. Re-run this script to demo warm-load speed.")


if __name__ == "__main__":
    main()
