"""Sanity check: run QTApplier on 25 famous Chinese proper nouns
and compare against expected conventional Vietnamese readings.
"""

from __future__ import annotations

import logging
from pathlib import Path

from trilex.qt_dict.applier import QTApplier

ROOT = Path(__file__).resolve().parents[1]

# (chinese, conventional_vietnamese, category)
TEST_CASES: list[tuple[str, str, str]] = [
    # Journey to the West
    ("孙悟空",     "Tôn Ngộ Không",      "novel"),
    ("唐三藏",     "Đường Tam Tạng",     "novel"),
    ("猪八戒",     "Trư Bát Giới",       "novel"),
    ("沙和尚",     "Sa Hoà Thượng",      "novel"),
    # Dream of the Red Chamber
    ("林黛玉",     "Lâm Đại Ngọc",       "novel"),
    ("贾宝玉",     "Giả Bảo Ngọc",       "novel"),
    # Three Kingdoms
    ("诸葛亮",     "Gia Cát Lượng",      "history"),
    ("曹操",       "Tào Tháo",           "history"),
    ("关羽",       "Quan Vũ",            "history"),
    ("张飞",       "Trương Phi",         "history"),
    ("刘备",       "Lưu Bị",             "history"),
    ("周瑜",       "Chu Du",             "history"),
    # Poets / Emperors
    ("李白",       "Lý Bạch",            "poet"),
    ("杜甫",       "Đỗ Phủ",             "poet"),
    ("秦始皇",     "Tần Thuỷ Hoàng",     "emperor"),
    ("武则天",     "Vũ Tắc Thiên",       "emperor"),
    # Mythology
    ("玉皇大帝",   "Ngọc Hoàng Đại Đế",  "myth"),
    ("观音",       "Quan Âm",            "myth"),
    ("嫦娥",       "Hằng Nga",           "myth"),
    ("太上老君",   "Thái Thượng Lão Quân","myth"),
    # Geography
    ("北京",       "Bắc Kinh",           "place"),
    ("上海",       "Thượng Hải",         "place"),
    ("长城",       "Trường Thành",       "place"),
    ("黄河",       "Hoàng Hà",           "place"),
    ("长江",       "Trường Giang",       "place"),
]


def _normalize(s: str) -> str:
    return s.strip().lower().replace("  ", " ")


def main() -> None:
    logging.basicConfig(level=logging.ERROR)
    applier = QTApplier(
        ROOT / "data" / "dictionaries", cache_dir=ROOT / "data" / "cache"
    )

    print(f"{'#':<3} {'Source':<10} {'Expected':<22} {'Actual':<28} {'Match'}")
    print("-" * 80)
    pass_count = 0
    for i, (zh, expected, category) in enumerate(TEST_CASES, 1):
        actual = applier.convert(zh)
        # Compare case-insensitively, ignore extra spaces
        ok = _normalize(actual) == _normalize(expected)
        if ok:
            pass_count += 1
        flag = "OK" if ok else "MISS"
        print(f"{i:<3} {zh:<10} {expected:<22} {actual:<28} {flag}  [{category}]")

    print("-" * 80)
    pct = pass_count / len(TEST_CASES) * 100
    print(f"Result: {pass_count}/{len(TEST_CASES)} match ({pct:.0f}%)")


if __name__ == "__main__":
    main()
