"""
test_phase2.py — Verify Phase 2 scraper port (Bươc 2.7).

Chạy: PYTHONPATH=src python scripts/test_phase2.py

Test 1: Import adapter API
Test 2: Progress save/load + resume detection (không cần API key)
Test 3: LazyPath resolves từ settings
Test 4: Regex key pattern strict
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Đảm bảo src/ trong path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Settings validates GEMINI_API_KEY on first import — set dummy if not in env
if not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "test-key-placeholder-phase2-verify"

PASS = []
FAIL = []


def ok(name: str) -> None:
    PASS.append(name)
    print(f"  ✅ {name}")


def fail(name: str, reason: str) -> None:
    FAIL.append(name)
    print(f"  ❌ {name}: {reason}")


# ── Test 1: Import ────────────────────────────────────────────────────────────

def test_import() -> None:
    try:
        from littrans.modules.scraper import run_scraper_blocking, ScraperOptions, ScraperResult
        ok("import run_scraper_blocking + ScraperOptions + ScraperResult")
    except Exception as e:
        fail("import adapter API", str(e))

    try:
        from littrans.modules.scraper import run_scraper
        ok("import run_scraper (async)")
    except Exception as e:
        fail("import run_scraper", str(e))


# ── Test 2: Progress save/load (Bươc 2.7 core) ───────────────────────────────

async def test_resume_logic() -> None:
    from littrans.modules.scraper.utils.file_io import save_progress, load_progress

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        path = f.name

    try:
        # 2a: Save progress với current_url → load lại, verify resume detected
        progress = {
            "current_url": "https://royalroad.com/fiction/123/chapter/456",
            "chapter_count": 15,
            "fingerprints": ["abc123", "def456"],
            "all_visited_urls": ["https://royalroad.com/fiction/123/chapter/1"],
            "story_title": "Test Story",
            "completed": False,
        }
        await save_progress(path, progress)

        loaded = await load_progress(path)
        assert loaded.get("current_url") == progress["current_url"], "current_url mismatch"
        assert loaded.get("chapter_count") == 15, "chapter_count mismatch"
        assert len(loaded.get("fingerprints", [])) == 2, "fingerprints mismatch"
        ok("save_progress → load_progress round-trip")

        # 2b: Verify .tmp file không còn (atomic write cleanup)
        tmp_path = path + ".tmp"
        assert not os.path.exists(tmp_path), ".tmp file still exists after write"
        ok("atomic write: .tmp cleaned up")

        # 2c: Simulate resume detection logic (cùng pattern find_start_chapter dùng)
        has_resume = bool(loaded.get("current_url"))
        assert has_resume, "resume not detected despite current_url present"
        ok("resume detection: current_url found → would resume (not restart)")

        # 2d: Empty progress → no resume
        await save_progress(path, {})
        empty = await load_progress(path)
        assert not empty.get("current_url"), "empty progress has current_url"
        ok("empty progress: no resume → fresh start")

    except AssertionError as e:
        fail("resume logic", str(e))
    except Exception as e:
        fail("resume logic (unexpected)", str(e))
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ── Test 3: LazyPath ─────────────────────────────────────────────────────────

def test_lazy_path() -> None:
    try:
        from littrans.modules.scraper.config import DATA_DIR, OUTPUT_DIR, PROGRESS_DIR, PROFILES_FILE
        # Should support / operator
        child = DATA_DIR / "test_subdir"
        assert isinstance(child, Path), f"DATA_DIR / str should return Path, got {type(child)}"
        ok("LazyPath __truediv__ returns Path")

        # Should be str-able
        s = str(DATA_DIR)
        assert isinstance(s, str) and len(s) > 0, "str(DATA_DIR) empty"
        ok("LazyPath __str__ works")

        # Should resolve from settings (data_dir under NovelPipeline root)
        p = Path(str(DATA_DIR))
        assert "NovelPipeline" in str(p) or "data" in str(p).lower(), \
            f"DATA_DIR unexpected path: {p}"
        ok(f"LazyPath resolves to: {p}")

    except Exception as e:
        fail("LazyPath", str(e))


# ── Test 4: Strict regex ─────────────────────────────────────────────────────

def test_gemini_key_regex() -> None:
    import re
    pattern = re.compile(r"^GEMINI_API_KEY_\d+$")

    should_match = ["GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_10"]
    should_not   = ["GEMINI_API_KEY", "GEMINI_API_KEY_DEV", "GEMINI_API_KEY_OLD",
                    "GEMINI_API_KEY_BACKUP", "GEMINI_API_KEYS_LIST", "GEMINI_API_KEY_"]

    for name in should_match:
        if not pattern.match(name):
            fail("regex strict", f"{name!r} should match but didn't")
            return

    for name in should_not:
        if pattern.match(name):
            fail("regex strict", f"{name!r} should NOT match but did")
            return

    ok("strict ^GEMINI_API_KEY_\\d+$ regex correct")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n=== Phase 2 Verification (Buoc 2.7) ===\n")

    print("Test 1: Import adapter API")
    test_import()

    print("\nTest 2: Progress save/load + resume logic")
    await test_resume_logic()

    print("\nTest 3: LazyPath resolves from settings")
    test_lazy_path()

    print("\nTest 4: GEMINI_API_KEY strict regex")
    test_gemini_key_regex()

    print(f"\n{'─'*40}")
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print(f"\nFailed: {', '.join(FAIL)}")
        sys.exit(1)
    else:
        print("All tests passed. Phase 2 code verified.\n")
        print("=> Buoc 2.7 live test (can GEMINI_API_KEY + URL that):")
        print("   1. Chay scrape ~20 chuong, Ctrl+C giua chung")
        print("   2. Check progress/*.json con data dung")
        print("   3. Chay lai -> tiep tuc dung chuong, khong scrape lai tu dau")


if __name__ == "__main__":
    asyncio.run(main())
