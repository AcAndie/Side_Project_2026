"""Dictionary page — list and upload QT-format .txt dictionaries."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from trilex.qt_dict.parser import QTParseError, parse_qt_dict
from trilex.ui._helpers import sidebar_project_selector

st.set_page_config(page_title="Dictionary — TriLex", page_icon="📖", layout="wide")

sidebar_project_selector()

st.title("📖 Dictionary")

DICT_DIR = Path("data/dictionaries")
DICT_DIR.mkdir(parents=True, exist_ok=True)

st.caption(f"Folder hiện tại: `{DICT_DIR.resolve()}`")

# --------------------------------------------------------------------------- #
# Listing                                                                     #
# --------------------------------------------------------------------------- #

files = sorted(DICT_DIR.glob("*.txt"))
if not files:
    st.info("Chưa có file .txt nào trong folder. Upload bên dưới.")
else:
    rows = []
    total_entries = 0
    total_bytes = 0
    for f in files:
        size = f.stat().st_size
        total_bytes += size
        try:
            qt = parse_qt_dict(f)
            count = qt.meta.count
            skipped = qt.meta.skipped_lines
            encoding = qt.meta.encoding
            err = ""
        except QTParseError as e:
            count, skipped, encoding, err = 0, 0, "?", str(e)
        total_entries += count
        rows.append(
            {
                "file": f.name,
                "size_kb": round(size / 1024, 1),
                "entries": count,
                "skipped": skipped,
                "encoding": encoding,
                "error": err[:60],
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    cols = st.columns(3)
    cols[0].metric("Tổng file", len(files))
    cols[1].metric("Tổng entries", f"{total_entries:,}")
    cols[2].metric("Tổng size", f"{total_bytes / 1024 / 1024:.1f} MB")

st.divider()

# --------------------------------------------------------------------------- #
# Upload                                                                      #
# --------------------------------------------------------------------------- #

st.subheader("⬆️ Upload file dictionary mới")
uploaded = st.file_uploader(
    "QT-format .txt (VietPhrase.txt / Names.txt / LuatNhan.txt / ...)",
    type=["txt"],
    accept_multiple_files=True,
)
if uploaded:
    for f in uploaded:
        target = DICT_DIR / f.name
        target.write_bytes(f.getvalue())
        st.success(f"Đã ghi {target.name} ({len(f.getvalue()):,} bytes)")
    st.rerun()
