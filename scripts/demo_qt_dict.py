"""One-off demo: load Vietphrase.txt and print stats + samples."""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trilex.qt_dict import parse_qt_dict  # noqa: E402

logging.basicConfig(level=logging.ERROR)  # silence header-line warnings


def main() -> None:
    p = ROOT / "data" / "dictionaries" / "Vietphrase.txt"
    d = parse_qt_dict(p)

    print(f"Source           : {d.meta.source}")
    print(f"Encoding         : {d.meta.encoding}")
    print(f"Separator picked : {d.meta.separator!r}")
    print(f"Total entries    : {d.meta.count:,}")
    print(f"Skipped lines    : {d.meta.skipped_lines:,}")
    print()

    random.seed(42)
    sample_keys = random.sample(list(d.entries.keys()), 5)
    print("=== 5 random entries ===")
    for k in sample_keys:
        vals = d.entries[k]
        shown = "; ".join(vals[:3]) + (" ..." if len(vals) > 3 else "")
        print(f"  {k!r:30s} -> {shown}  (n={len(vals)})")
    print()

    longest = sorted(d.entries.items(), key=lambda kv: len(kv[0]), reverse=True)[:5]
    print("=== 5 longest keys ===")
    for k, vals in longest:
        print(f"  len={len(k):3d}  {k!r}")
        print(f"          -> {vals[0]!r}")


if __name__ == "__main__":
    main()
