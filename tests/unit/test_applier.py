"""Unit tests for QTApplier."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from trilex.qt_dict.applier import QTApplier


def _write(path: Path, content: str) -> None:
    path.write_bytes(content.encode("utf-8"))


@pytest.fixture
def tu_tien_dicts(tmp_path: Path) -> Path:
    """Synthetic mini QT dict bundle covering all tiers."""
    d = tmp_path / "dicts"
    d.mkdir()
    _write(d / "Names.txt", "李青=Lý Thanh\n青云宗=Thanh Vân Tông\n")
    _write(d / "Names2.txt", "金丹大道=Kim Đan Đại Đạo\n")
    _write(d / "Vietphrase.txt", "走进了=đi vào\n修炼=tu luyện\n")
    _write(
        d / "ChinesePhienAmWords.txt",
        "李=lý\n青=thanh\n走=tẩu\n进=tiến\n了=liễu\n云=vân\n宗=tông\n开=khai\n始=thủy\n",
    )
    _write(d / "LuatNhan.txt", "不比{0}强=không mạnh bằng {0}\n")
    return d


def test_basic_convert_chains_tiers(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("李青走进了青云宗")
    assert "Lý Thanh" in out
    assert "Thanh Vân Tông" in out
    assert "đi vào" in out
    assert all(not ("一" <= c <= "鿿") for c in out)


def test_custom_glossary_overrides_tier(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("李青走进了青云宗", custom_glossary={"李青": "Li Qing"})
    assert "Li Qing" in out
    assert "Lý Thanh" not in out


def test_luat_nhan_pre_pass_with_placeholder(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("不比金丹大道强")
    assert "không mạnh bằng" in out
    assert "Kim Đan Đại Đạo" in out


def test_char_fallback_when_no_compound(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("开始")
    assert "khai" in out
    assert "thủy" in out


def test_empty_text_returns_empty(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    assert applier.convert("") == ""


def test_verbose_logs_matches(
    tu_tien_dicts: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    with caplog.at_level(logging.INFO, logger="trilex.qt_dict.applier"):
        applier.convert("李青", verbose=True)
    assert any("[names]" in r.getMessage() for r in caplog.records)


def test_punctuation_preserved(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("李青，青云宗。")
    assert "，" in out
    assert "。" in out


def test_unmatched_chars_preserved(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("李青XYZ青云宗")
    assert "XYZ" in out


def test_missing_optional_dicts_still_works(tmp_path: Path) -> None:
    d = tmp_path / "dicts"
    d.mkdir()
    _write(d / "ChinesePhienAmWords.txt", "李=lý\n青=thanh\n")
    applier = QTApplier(d, cache_dir=tmp_path / "cache")
    out = applier.convert("李青")
    assert "lý" in out
    assert "thanh" in out
    assert applier.tier_names == ["phienam"]


def test_higher_tier_wins_over_lower(tu_tien_dicts: Path, tmp_path: Path) -> None:
    """Names tier (capitalized) should beat PhienAm tier (lowercase) for same span."""
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    out = applier.convert("李青")
    assert "Lý Thanh" in out
    assert "lý" not in out  # PhienAm should not apply where Names matched


def test_tier_names_order(tu_tien_dicts: Path, tmp_path: Path) -> None:
    applier = QTApplier(tu_tien_dicts, cache_dir=tmp_path / "cache")
    assert applier.tier_names == ["names", "vietphrase", "phienam"]
