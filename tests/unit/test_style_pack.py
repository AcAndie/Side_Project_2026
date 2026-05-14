"""Tests for the style-pack loader + the shipped `tu_tien.vn.yaml`."""

from __future__ import annotations

from pathlib import Path

import pytest

from trilex.core.style_pack import (
    DEFAULT_PACKS_DIR,
    StylePack,
    StylePackError,
    get_style_pack,
    load_style_pack,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TU_TIEN_PATH = PROJECT_ROOT / "packs" / "style" / "tu_tien.vn.yaml"


# --------------------------------------------------------------------------- #
# Real pack — shape contract                                                  #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def tu_tien_pack() -> StylePack:
    return load_style_pack(TU_TIEN_PATH)


def test_real_pack_loads(tu_tien_pack: StylePack) -> None:
    assert tu_tien_pack.source_langs == ["zh"]
    assert tu_tien_pack.target_lang == "vn"
    assert tu_tien_pack.genre == "tu_tien"
    assert tu_tien_pack.name.startswith("Tu Tiên")


def test_realm_ladder_has_nine_canonical_tiers(tu_tien_pack: StylePack) -> None:
    assert len(tu_tien_pack.realm_ladder) == 9
    expected_zh = ["练气", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫"]
    assert [r.zh for r in tu_tien_pack.realm_ladder] == expected_zh
    assert tu_tien_pack.realm_ladder[2].vn == "Kim Đan"
    ranks = [r.rank for r in tu_tien_pack.realm_ladder]
    assert ranks == sorted(ranks)


def test_vocabulary_rules_have_real_entries(tu_tien_pack: StylePack) -> None:
    assert tu_tien_pack.vocabulary_rules.prefer_han_viet is True
    examples = tu_tien_pack.vocabulary_rules.examples
    assert len(examples) >= 20
    zh_keys = {e.zh for e in examples}
    for must_have in ["修为", "境界", "灵气", "法宝", "神识"]:
        assert must_have in zh_keys


def test_honorifics_cover_basic_relations(tu_tien_pack: StylePack) -> None:
    zh_keys = {h.zh for h in tu_tien_pack.honorifics}
    for must_have in ["道友", "前辈", "师父", "师兄", "师妹"]:
        assert must_have in zh_keys


def test_sect_suffixes_include_canonical(tu_tien_pack: StylePack) -> None:
    suffixes = tu_tien_pack.sect_suffixes
    for must_have in ["tông", "phái", "môn", "các"]:
        assert must_have in suffixes


def test_banned_phrases_catch_translationese(tu_tien_pack: StylePack) -> None:
    banned = set(tu_tien_pack.banned_phrases)
    for must_have in ["một cách", "đang được", "phép thuật", "thuốc viên"]:
        assert must_have in banned


def test_preferred_phrases_have_avoid_pair(tu_tien_pack: StylePack) -> None:
    pairs = tu_tien_pack.preferred_phrases
    assert any(p.preferred == "linh khí" and p.avoid for p in pairs)
    assert any(p.preferred == "pháp bảo" and p.avoid for p in pairs)


def test_few_shot_examples_are_aligned(tu_tien_pack: StylePack) -> None:
    examples = tu_tien_pack.few_shot_examples
    assert len(examples) >= 4
    for ex in examples:
        assert ex.source.strip()
        assert ex.target.strip()


def test_quality_checks_forbid_banned_terms(tu_tien_pack: StylePack) -> None:
    forbidden = set(tu_tien_pack.quality_checks.forbidden_in_output)
    assert "phép thuật" in forbidden


def test_pack_is_immutable(tu_tien_pack: StylePack) -> None:
    with pytest.raises(Exception):  # noqa: B017
        tu_tien_pack.name = "x"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Loader — error paths + caching                                              #
# --------------------------------------------------------------------------- #


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(StylePackError, match="not found"):
        load_style_pack(tmp_path / "nope.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    p = tmp_path / "broken.yaml"
    p.write_text("foo: [unclosed", encoding="utf-8")
    with pytest.raises(StylePackError, match="YAML parse"):
        load_style_pack(p)


def test_non_mapping_root_raises(tmp_path: Path) -> None:
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(StylePackError, match="must be a mapping"):
        load_style_pack(p)


def test_target_lang_in_source_langs_rejected(tmp_path: Path) -> None:
    p = tmp_path / "selfloop.yaml"
    p.write_text("name: bad\nsource_langs: [vn]\ntarget_lang: vn\n", encoding="utf-8")
    with pytest.raises(StylePackError):
        load_style_pack(p)


def test_empty_source_langs_rejected(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("name: bad\nsource_langs: []\ntarget_lang: vn\n", encoding="utf-8")
    with pytest.raises(StylePackError):
        load_style_pack(p)


def test_unordered_realm_ranks_rejected(tmp_path: Path) -> None:
    p = tmp_path / "ranks.yaml"
    p.write_text(
        "name: bad\n"
        "source_langs: [zh]\n"
        "target_lang: vn\n"
        "realm_ladder:\n"
        "  - {zh: a, vn: A, rank: 2}\n"
        "  - {zh: b, vn: B, rank: 1}\n",
        encoding="utf-8",
    )
    with pytest.raises(StylePackError, match="monotonically"):
        load_style_pack(p)


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    p = tmp_path / "extra.yaml"
    p.write_text(
        "name: ok\n" "source_langs: [zh]\n" "target_lang: vn\n" "future_field_we_dont_know: 42\n",
        encoding="utf-8",
    )
    pack = load_style_pack(p)
    assert pack.name == "ok"


def test_get_style_pack_finds_shipped_pack() -> None:
    get_style_pack.cache_clear()
    pack = get_style_pack("tu_tien", "vn", packs_dir=DEFAULT_PACKS_DIR)
    assert pack.genre == "tu_tien"


def test_get_style_pack_missing_raises(tmp_path: Path) -> None:
    get_style_pack.cache_clear()
    with pytest.raises(StylePackError):
        get_style_pack("nonexistent_genre", "vn", packs_dir=tmp_path)
