"""Unit tests for AhoMatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from trilex.qt_dict.automaton import (
    AhoMatcher,
    cache_path_for,
    load_or_build,
)


@pytest.fixture
def tu_tien_entries() -> dict[str, str]:
    return {
        "金丹": "Kim Đan",
        "金丹期": "thời kỳ Kim Đan",
        "丹田": "Đan Điền",
        "大道": "Đại Đạo",
        "灵气": "linh khí",
    }


def test_find_all_returns_all_matches(tu_tien_entries: dict[str, str]) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    text = "他到了金丹期就突破。"
    matches = m.find_all(text)
    keys = sorted(x.key for x in matches)
    assert keys == ["金丹", "金丹期"]  # both overlapping spans surfaced


def test_find_all_positions_are_correct(tu_tien_entries: dict[str, str]) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    text = "他到了金丹期。"  # "金丹期" at indices 3..6
    matches = m.find_all(text)
    by_key = {x.key: x for x in matches}
    assert by_key["金丹期"].start == 3
    assert by_key["金丹期"].end == 6
    assert text[by_key["金丹期"].start : by_key["金丹期"].end] == "金丹期"


def test_longest_non_overlapping_prefers_longer(
    tu_tien_entries: dict[str, str],
) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    text = "他突破金丹期了。"
    matches = m.find_longest_non_overlapping(text)
    keys = [x.key for x in matches]
    # "金丹期" (len 3) should win over "金丹" (len 2) at the same start
    assert "金丹期" in keys
    assert "金丹" not in keys


def test_longest_non_overlapping_jumps_cursor(
    tu_tien_entries: dict[str, str],
) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    text = "金丹大道灵气"  # 3 disjoint terms
    matches = m.find_longest_non_overlapping(text)
    assert [x.key for x in matches] == ["金丹", "大道", "灵气"]


def test_empty_text_returns_empty(tu_tien_entries: dict[str, str]) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    assert m.find_all("") == []
    assert m.find_longest_non_overlapping("") == []


def test_no_match_returns_empty(tu_tien_entries: dict[str, str]) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    assert m.find_all("XXXYYY") == []


def test_unbuilt_matcher_raises() -> None:
    m = AhoMatcher()
    assert m.is_built is False
    with pytest.raises(RuntimeError):
        m.find_all("anything")
    with pytest.raises(RuntimeError):
        m.stats()


def test_stats_populated_after_build(tu_tien_entries: dict[str, str]) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    s = m.stats()
    assert s.word_count == len(tu_tien_entries)
    assert s.build_seconds >= 0.0


def test_save_load_round_trip(tmp_path: Path, tu_tien_entries: dict[str, str]) -> None:
    m = AhoMatcher()
    m.build(tu_tien_entries)
    cache_file = tmp_path / "auto.pkl"
    m.save(cache_file)

    m2 = AhoMatcher.load(cache_file)
    assert m2.is_built
    matches = m2.find_longest_non_overlapping("金丹大道")
    assert [x.key for x in matches] == ["金丹", "大道"]


def test_cache_path_depends_on_content(tmp_path: Path) -> None:
    f1 = tmp_path / "a.txt"
    f1.write_bytes("金丹=Kim Dan\n".encode())
    f2 = tmp_path / "b.txt"
    f2.write_bytes("金丹=Kim Dan\n".encode())
    f3 = tmp_path / "c.txt"
    f3.write_bytes(b"different content\n")

    cache_dir = tmp_path / "cache"
    p1 = cache_path_for(f1, cache_dir)
    p2 = cache_path_for(f2, cache_dir)
    p3 = cache_path_for(f3, cache_dir)
    assert p1 == p2  # same content → same hash
    assert p1 != p3  # different content → different hash


def test_load_or_build_uses_cache_on_second_call(tmp_path: Path) -> None:
    dict_path = tmp_path / "src.txt"
    dict_path.write_bytes("金丹=Kim Dan\n".encode())
    cache_dir = tmp_path / "cache"
    entries = {"金丹": "Kim Đan"}

    m1 = load_or_build(entries, dict_path, cache_dir)
    cached_file = cache_path_for(dict_path, cache_dir)
    assert cached_file.exists()
    mtime1 = cached_file.stat().st_mtime

    m2 = load_or_build(entries, dict_path, cache_dir)
    assert cached_file.stat().st_mtime == mtime1  # not rewritten
    assert m1.find_all("金丹") and m2.find_all("金丹")
