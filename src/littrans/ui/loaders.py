"""
src/littrans/ui/loaders.py — Cached data loaders shared across UI pages.
Extracted from app.py (Batch 7).
"""
from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[3]


@st.cache_data(ttl=10)
def load_chapters(novel_name: str = "") -> list[dict]:
    try:
        from littrans.config.settings import settings
        input_dir  = settings.active_input_dir
        output_dir = settings.active_output_dir
    except Exception:
        input_dir  = _ROOT / "inputs"  / novel_name if novel_name else _ROOT / "inputs"
        output_dir = _ROOT / "outputs" / novel_name if novel_name else _ROOT / "outputs"
    if not input_dir.exists():
        return []
    files = sorted(
        [f for f in input_dir.iterdir() if f.suffix in (".txt", ".md")],
        key=lambda s: [int(t) if t.isdigit() else t.lower()
                       for t in re.split(r"(\d+)", s.name)],
    )
    result = []
    for i, fp in enumerate(files):
        vn_path = output_dir / f"{fp.stem}_VN.txt"
        result.append({
            "idx": i, "name": fp.name, "path": fp,
            "size": f"{fp.stat().st_size // 1024} KB",
            "vn_path": vn_path, "done": vn_path.exists(),
        })
    return result


@st.cache_data(ttl=30)
def load_chapter_content(path_str: str, vn_path_str: str, done: bool) -> dict[str, str]:
    raw = vn = ""
    try:    raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except: pass
    if done:
        try:    vn = Path(vn_path_str).read_text(encoding="utf-8", errors="replace")
        except: pass
    return {"raw": raw, "vn": vn}


@st.cache_data(ttl=4)
def load_characters(novel_name: str = "") -> dict[str, dict]:
    try:
        from littrans.context.characters import load_active, load_archive
        return {
            "active" : load_active().get("characters", {}),
            "archive": load_archive().get("characters", {}),
        }
    except Exception:
        return {"active": {}, "archive": {}}


@st.cache_data(ttl=4)
def load_glossary_data(novel_name: str = "") -> dict[str, list[tuple[str, str]]]:
    try:
        from littrans.context.glossary import _load_all
        raw = _load_all()
    except Exception:
        return {}
    result: dict[str, list] = {}
    for cat, terms in raw.items():
        entries = []
        for _, line in terms.items():
            clean = re.sub(r"^[\*\-\+]\s*", "", line.strip())
            if ":" in clean and not clean.startswith("#"):
                eng, _, vn = clean.partition(":")
                if eng.strip():
                    entries.append((eng.strip(), vn.strip()))
        if entries:
            result[cat] = entries
    return result


@st.cache_data(ttl=5)
def load_stats(novel_name: str = "") -> dict:
    try:
        from littrans.context.characters import character_stats
        from littrans.context.glossary   import glossary_stats
        from littrans.context.skills     import skills_stats
        from littrans.context.name_lock  import lock_stats
        return {
            "chars" : character_stats(),
            "glos"  : glossary_stats(),
            "skills": skills_stats(),
            "lock"  : lock_stats(),
        }
    except Exception:
        return {"chars": {}, "glos": {}, "skills": {}, "lock": {}}
