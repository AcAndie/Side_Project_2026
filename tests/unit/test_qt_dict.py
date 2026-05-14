"""Unit tests for QT dictionary parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from trilex.qt_dict.parser import QTParseError, parse_qt_dict


def _write_utf8(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_vietphrase_semicolon(tmp_path: Path) -> None:
    f = _write_utf8(tmp_path / "vp.txt", "金丹=Kim Đan;Golden Core\n大道=Đại Đạo\n")
    d = parse_qt_dict(f)
    assert d.meta.separator == ";"
    assert d.meta.count == 2
    assert d.entries["金丹"] == ["Kim Đan", "Golden Core"]
    assert d.entries["大道"] == ["Đại Đạo"]
    assert "金丹" in d


def test_parses_pronouns_slash_separator(tmp_path: Path) -> None:
    f = _write_utf8(tmp_path / "pn.txt", "他们=bọn hắn/chúng nó/họ\n你们=các ngươi/các người\n")
    d = parse_qt_dict(f)
    assert d.meta.separator == "/"
    assert d.entries["他们"] == ["bọn hắn", "chúng nó", "họ"]
    assert d.entries["你们"] == ["các ngươi", "các người"]


def test_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    content = "# header comment\n\n金丹=Kim Đan\n# inline comment\n大道=Đại Đạo\n\n"
    f = _write_utf8(tmp_path / "c.txt", content)
    d = parse_qt_dict(f)
    assert d.meta.count == 2
    assert d.meta.skipped_lines == 0


def test_warns_and_skips_malformed_no_equals(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    content = "金丹=Kim Đan\nthis line has no equals\n大道=Đại Đạo\n"
    f = _write_utf8(tmp_path / "m.txt", content)
    with caplog.at_level("WARNING"):
        d = parse_qt_dict(f)
    assert d.meta.count == 2
    assert d.meta.skipped_lines == 1
    assert any("no '='" in r.getMessage() for r in caplog.records)


def test_skips_empty_key_or_value(tmp_path: Path) -> None:
    content = "金丹=Kim Đan\n=lonely value\nlonely key=\n大道=Đại Đạo\n"
    f = _write_utf8(tmp_path / "e.txt", content)
    d = parse_qt_dict(f)
    assert d.meta.count == 2
    assert d.meta.skipped_lines == 2


def test_single_meaning_no_separator(tmp_path: Path) -> None:
    f = _write_utf8(tmp_path / "s.txt", "一=nhất\n二=nhị\n三=tam\n")
    d = parse_qt_dict(f)
    assert d.meta.count == 3
    assert d.entries["一"] == ["nhất"]
    assert d.entries["三"] == ["tam"]


def test_utf8_with_bom(tmp_path: Path) -> None:
    f = tmp_path / "bom.txt"
    f.write_bytes("﻿金丹=Kim Đan\n".encode())
    d = parse_qt_dict(f)
    assert "金丹" in d.entries
    assert d.meta.encoding == "utf-8-sig"


def test_utf16_fallback(tmp_path: Path) -> None:
    f = tmp_path / "u16.txt"
    f.write_bytes("金丹=Kim Đan\n大道=Đại Đạo\n".encode("utf-16"))
    d = parse_qt_dict(f)
    assert d.meta.encoding == "utf-16"
    assert d.entries["金丹"] == ["Kim Đan"]


def test_luatnhan_placeholder_preserved(tmp_path: Path) -> None:
    content = "不比{0}强=không mạnh bằng {0}\n打{0}一顿=đánh {0} một trận\n"
    f = _write_utf8(tmp_path / "ln.txt", content)
    d = parse_qt_dict(f)
    assert d.entries["不比{0}强"] == ["không mạnh bằng {0}"]
    assert d.entries["打{0}一顿"] == ["đánh {0} một trận"]


def test_strips_whitespace_around_key_value(tmp_path: Path) -> None:
    f = _write_utf8(tmp_path / "w.txt", "  金丹  =  Kim Đan  ;  Golden Core  \n")
    d = parse_qt_dict(f)
    assert d.entries["金丹"] == ["Kim Đan", "Golden Core"]


def test_undecodable_file_raises(tmp_path: Path) -> None:
    f = tmp_path / "bad.bin"
    # Bytes that decode under utf-8-sig / utf-16 / gbk = none.
    # 0xC0 0xC0 alone is invalid utf-8 start; gbk requires lead byte 0x81-0xFE
    # followed by valid trail — 0xC0 0xC0 happens to be valid GBK actually.
    # Use truly hostile pattern: utf-16 needs even length; len 3 odd → utf-16 fails.
    # utf-8-sig fails on 0xFF 0xFE (BOM-like) but utf-16 with BOM would succeed if
    # length even. Three bytes triggers utf-16 odd-length error and 0xFF is bad utf-8.
    f.write_bytes(b"\xff\xfe\xff")
    with pytest.raises(QTParseError):
        parse_qt_dict(f)


def test_dunder_len_matches_count(tmp_path: Path) -> None:
    f = _write_utf8(tmp_path / "l.txt", "a=1\nb=2\nc=3\n")
    d = parse_qt_dict(f)
    assert len(d) == 3 == d.meta.count
