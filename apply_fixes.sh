#!/bin/bash
# apply_fixes.sh — Chạy từ project root để apply tất cả fixes
# Usage: bash apply_fixes.sh
set -e

echo "=== LiTTrans Bug Fixes ==="
echo ""

# ── Kiểm tra đang ở đúng thư mục ─────────────────────────────────
if [ ! -f "src/littrans/ui/app.py" ]; then
    echo "❌ Không tìm thấy src/littrans/ui/app.py"
    echo "   Hãy chạy script này từ project root."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════
# FIX 1: app.py — render_bible thiếu argument S
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 1: app.py render_bible(S) ────────────────────────────"

if grep -q '"bible"     : render_bible,' src/littrans/ui/app.py; then
    # Fix dòng sai indentation + missing argument
    sed -i 's/    "bible"     : render_bible,/        "bible"     : lambda: render_bible(S),/' src/littrans/ui/app.py
    echo "  ✅ Fixed: render_bible → lambda: render_bible(S)"
elif grep -q '"bible"     : lambda: render_bible(S),' src/littrans/ui/app.py; then
    echo "  ⏭  Đã fix rồi, bỏ qua."
else
    echo "  ⚠️  Không tìm thấy pattern — kiểm tra thủ công."
fi

# Fix indentation _pages bible entry
if grep -q '"bible"     : "📖  Bible",' src/littrans/ui/app.py; then
    # Check if it has wrong indentation (8 spaces instead of 12)
    if grep -qP '^        "bible"     : "📖  Bible",' src/littrans/ui/app.py; then
        sed -i 's/^        "bible"     : "📖  Bible",/            "bible"     : "📖  Bible",/' src/littrans/ui/app.py
        echo "  ✅ Fixed: _pages indentation"
    fi
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 2: pipeline.py — import sai trong _final_merge
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 2: pipeline.py _final_merge imports ──────────────────"

PIPELINE="src/littrans/core/pipeline.py"

if grep -q "from littrans.cli.tool_clean import clean_glossary" "$PIPELINE"; then
    sed -i 's/from littrans.cli.tool_clean import clean_glossary/from littrans.cli.tool_clean_glossary import clean_glossary/' "$PIPELINE"
    echo "  ✅ Fixed: tool_clean → tool_clean_glossary"
else
    echo "  ⏭  clean_glossary import OK, bỏ qua."
fi

if grep -q "from littrans.cli.tool_clean import run_action" "$PIPELINE"; then
    sed -i 's/from littrans.cli.tool_clean import run_action/from littrans.cli.tool_clean_chars import run_action/' "$PIPELINE"
    echo "  ✅ Fixed: tool_clean → tool_clean_chars"
else
    echo "  ⏭  run_action import OK, bỏ qua."
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 3: utils/text_normalizer.py — thay bằng redirect shim
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 3: utils/text_normalizer.py → redirect shim ─────────"

UTILS_NORM="src/littrans/utils/text_normalizer.py"
CORE_NORM="src/littrans/core/text_normalizer.py"

if [ -f "$CORE_NORM" ]; then
    # Kiểm tra xem utils có phải là bản copy y hệt core không
    if diff -q "$UTILS_NORM" "$CORE_NORM" > /dev/null 2>&1; then
        cat > "$UTILS_NORM" << 'SHIM'
"""
src/littrans/utils/text_normalizer.py — Redirect shim.

[v5.3 Refactor] File đã chuyển về core/text_normalizer.py.
Giữ lại để không break import cũ. Không sửa file này.
"""
from littrans.core.text_normalizer import (  # noqa: F401
    normalize,
)
__all__ = ["normalize"]
SHIM
        echo "  ✅ Replaced duplicate với redirect shim (60 lines → 10 lines)"
    else
        echo "  ⚠️  utils và core KHÁC NHAU — không tự động replace, kiểm tra thủ công"
    fi
else
    echo "  ⚠️  core/text_normalizer.py không tồn tại"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 4: utils/post_processor.py — thay bằng redirect shim
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 4: utils/post_processor.py → redirect shim ──────────"

UTILS_PP="src/littrans/utils/post_processor.py"
CORE_PP="src/littrans/core/post_processor.py"

if [ -f "$CORE_PP" ]; then
    if diff -q "$UTILS_PP" "$CORE_PP" > /dev/null 2>&1; then
        cat > "$UTILS_PP" << 'SHIM'
"""
src/littrans/utils/post_processor.py — Redirect shim.

[v5.3 Refactor] File đã chuyển về core/post_processor.py.
Giữ lại để không break import cũ. Không sửa file này.
"""
from littrans.core.post_processor import (  # noqa: F401
    run,
    report,
)
__all__ = ["run", "report"]
SHIM
        echo "  ✅ Replaced duplicate với redirect shim"
    else
        echo "  ⚠️  utils và core KHÁC NHAU — không tự động replace, kiểm tra thủ công"
    fi
else
    echo "  ⚠️  core/post_processor.py không tồn tại"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 5: reset.py (root) — file rỗng
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 5: reset.py (root) ───────────────────────────────────"

if [ -f "reset.py" ] && [ ! -s "reset.py" ]; then
    cat > "reset.py" << 'WRAPPER'
"""
reset.py — Entry point redirect.
Script reset thực tế: scripts/reset.py

Dùng:
    python reset.py
    python reset.py --full
    python reset.py --list
"""
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).parent / "scripts" / "reset.py"
    if not script.exists():
        print(f"❌ Không tìm thấy: {script}")
        sys.exit(1)
    sys.exit(subprocess.run([sys.executable, str(script)] + sys.argv[1:]).returncode)
WRAPPER
    echo "  ✅ Fixed: reset.py không còn rỗng"
elif [ ! -f "reset.py" ]; then
    echo "  ⏭  reset.py không tồn tại, bỏ qua."
else
    echo "  ⏭  reset.py đã có nội dung."
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 6: .env.example — xóa USE_THREE_CALL đã deprecated
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 6: .env.example — xóa USE_THREE_CALL ────────────────"

if grep -q "USE_THREE_CALL" .env.example; then
    sed -i '/USE_THREE_CALL/d' .env.example
    echo "  ✅ Removed: USE_THREE_CALL (deprecated v5.2)"
else
    echo "  ⏭  Không có USE_THREE_CALL, bỏ qua."
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Tất cả fixes đã apply."
echo ""
echo "  Verify bằng lệnh:"
echo "    python -c \"from littrans.core.pipeline import Pipeline; print('pipeline OK')\""
echo "    python -c \"from littrans.ui.app import main; print('app OK')\""
echo "═══════════════════════════════════════════════════════"

# ═══════════════════════════════════════════════════════════════════
# FIX 7: app.py — except (Exception, SystemExit) → except Exception
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 7: app.py except SystemExit ──────────────────────────"

APP="src/littrans/ui/app.py"
COUNT=$(grep -c "except (Exception, SystemExit)" "$APP" 2>/dev/null || echo 0)

if [ "$COUNT" -gt "0" ]; then
    sed -i 's/except (Exception, SystemExit):/except Exception:/g' "$APP"
    echo "  ✅ Fixed $COUNT occurrences of 'except (Exception, SystemExit)'"
else
    echo "  ⏭  Không có SystemExit catch, bỏ qua."
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 8: app.py — USE_THREE_CALL toggle (dead UI control)
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 8: app.py USE_THREE_CALL dead toggle ─────────────────"

if grep -q "USE_THREE_CALL" "$APP"; then
    # Remove the three_call toggle lines (3 lines)
    python3 - << 'PYEOF'
import re

with open("src/littrans/ui/app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove the 3-line block: st.toggle + updates assignment for USE_THREE_CALL
# Pattern matches the toggle definition and its updates line
old_block = '''        st.markdown("#### Kiến trúc")
        three_call = st.toggle("3-call mode (Pre → Trans → Post)",
                               value=eb("USE_THREE_CALL", True),
                               help="USE_THREE_CALL")
        updates["USE_THREE_CALL"] = "true" if three_call else "false"'''

new_block = '''        st.markdown("#### Kiến trúc")
        st.info(
            "Pipeline luôn dùng **3-call flow** (Pre → Trans → Post). "
            "Mode duy nhất từ v5.2 — không có toggle.",
            icon="ℹ️",
        )'''

if old_block in content:
    content = content.replace(old_block, new_block)
    # Also remove disabled=not three_call from sliders
    content = content.replace(
        '                            help="PRE_CALL_SLEEP",  disabled=not three_call)',
        '                            help="PRE_CALL_SLEEP")',
    )
    content = content.replace(
        '                            help="POST_CALL_SLEEP", disabled=not three_call)',
        '                            help="POST_CALL_SLEEP")',
    )
    content = content.replace(
        '                                  help="POST_CALL_MAX_RETRIES", disabled=not three_call)',
        '                                  help="POST_CALL_MAX_RETRIES")',
    )
    content = content.replace(
        '                             help="TRANS_RETRY_ON_QUALITY", disabled=not three_call)',
        '                             help="TRANS_RETRY_ON_QUALITY")',
    )
    with open("src/littrans/ui/app.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("  ✅ Removed USE_THREE_CALL toggle + disabled params")
else:
    print("  ⚠️  Pattern not found — kiểm tra thủ công app.py Tab Pipeline")
PYEOF
else
    echo "  ⏭  USE_THREE_CALL không còn trong app.py."
fi

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 9: app.py — _poll() zombie thread guard
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 9: app.py _poll() zombie thread guard ────────────────"

python3 - << 'PYEOF'
with open("src/littrans/ui/app.py", "r", encoding="utf-8") as f:
    content = f.read()

old_poll = '''def _poll(q_key: str, logs_key: str) -> bool:
    """Drain queue → session state list. Returns True khi nhận __DONE__."""
    q: queue.Queue | None = S.get(q_key)
    if q is None:
        return False
    done = False
    while True:
        try:
            msg = q.get_nowait()
            if msg == "__DONE__":
                done = True
            else:
                S[logs_key].append(msg)
        except queue.Empty:
            break
    return done'''

new_poll = '''def _poll(q_key: str, logs_key: str, thread_key: str | None = None) -> bool:
    """
    Drain queue → session state list. Returns True khi nhận __DONE__.
    thread_key: session state key của thread — dùng để detect zombie thread.
    """
    q: queue.Queue | None = S.get(q_key)
    if q is None:
        return False
    done = False
    while True:
        try:
            msg = q.get_nowait()
            if msg == "__DONE__":
                done = True
            else:
                S[logs_key].append(msg)
        except queue.Empty:
            break
    # Zombie thread guard: thread đã chết mà không gửi __DONE__
    if not done and thread_key:
        thread = S.get(thread_key)
        if thread is not None and not thread.is_alive():
            S[logs_key].append("⚠️  Background thread đã dừng bất ngờ.")
            done = True
    return done'''

if old_poll in content:
    content = content.replace(old_poll, new_poll)
    # Update call sites to pass thread_key
    content = content.replace(
        'done_flag = _poll("log_q", "logs")',
        'done_flag = _poll("log_q", "logs", "run_thread")',
    )
    content = content.replace(
        'rt_done = _poll("rt_q", "rt_logs")',
        'rt_done = _poll("rt_q", "rt_logs", "rt_thread")',
    )
    with open("src/littrans/ui/app.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("  ✅ _poll() upgraded với zombie thread guard")
    print("  ✅ Call sites updated: run_thread, rt_thread")
else:
    print("  ⚠️  _poll() pattern not found — kiểm tra thủ công")
PYEOF

echo ""

# ═══════════════════════════════════════════════════════════════════
# FIX 10: app.py — load_chapters() I/O bottleneck (lazy load)
# ═══════════════════════════════════════════════════════════════════
echo "── Fix 10: app.py load_chapters() lazy loading ──────────────"

python3 - << 'PYEOF'
with open("src/littrans/ui/app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace load_chapters - remove raw/vn reads, change TTL
old_chapters_sig = '@st.cache_data(ttl=3)\ndef load_chapters() -> list[dict]:'

if old_chapters_sig not in content:
    print("  ⚠️  load_chapters signature not found with ttl=3 — may already be fixed")
else:
    # Replace ttl=3 with ttl=10
    content = content.replace(
        '@st.cache_data(ttl=3)\ndef load_chapters() -> list[dict]:',
        '@st.cache_data(ttl=10)\ndef load_chapters() -> list[dict]:',
    )

    # Remove the raw/vn lines from load_chapters result dict
    old_result = '''            "vn_path": vn_path,
            "done"   : vn_path.exists(),
            "raw"    : fp.read_text(encoding="utf-8", errors="replace"),
            "vn"     : vn_path.read_text(encoding="utf-8", errors="replace")
                       if vn_path.exists() else "",
        })'''

    new_result = '''            "vn_path": vn_path,
            "done"   : vn_path.exists(),
            # "raw" and "vn" are loaded lazily via load_chapter_content()
        })'''

    if old_result in content:
        content = content.replace(old_result, new_result)

        # Add load_chapter_content function after load_chapters
        lazy_loader = '''

@st.cache_data(ttl=30)
def load_chapter_content(path_str: str, vn_path_str: str, done: bool) -> dict[str, str]:
    """
    Lazy load: đọc nội dung file khi cần, cache 30s.
    Nhận str thay vì Path để st.cache_data hoạt động đúng.
    """
    raw = ""
    vn  = ""
    try:
        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if done:
        try:
            vn = Path(vn_path_str).read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return {"raw": raw, "vn": vn}

'''
        # Insert after load_chapters function (before load_characters)
        content = content.replace(
            '\n@st.cache_data(ttl=4)\ndef load_characters()',
            lazy_loader + '\n@st.cache_data(ttl=4)\ndef load_characters()',
        )

        # Update _render_chapter_detail to use lazy loader
        old_detail_sig = "def _render_chapter_detail(ch: dict) -> None:\n    # ── Meta strip"
        new_detail_sig = '''def _render_chapter_detail(ch: dict) -> None:
    # ── Lazy load nội dung file ────────────────────────────────────
    content = load_chapter_content(str(ch["path"]), str(ch["vn_path"]), ch["done"])
    raw = content["raw"]
    vn  = content["vn"]

    # ── Meta strip'''
        if old_detail_sig in content:
            content = content.replace(old_detail_sig, new_detail_sig)
            # Replace ch["raw"] and ch["vn"] references in _render_chapter_detail
            # These only appear after the function def, so simple replace is safe
            # for the scope of this function
            content = content.replace('ch["raw"]', 'raw')
            content = content.replace('ch["vn"]', 'vn')
            print("  ✅ load_chapters(): ttl 3s→10s, removed raw/vn reads")
            print("  ✅ load_chapter_content(): new lazy loader added (ttl=30s)")
            print("  ✅ _render_chapter_detail(): updated to use lazy loader")
        else:
            print("  ⚠️  _render_chapter_detail pattern not found")
    else:
        print("  ⚠️  load_chapters result dict pattern not found")

    with open("src/littrans/ui/app.py", "w", encoding="utf-8") as f:
        f.write(content)
PYEOF

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Phase 2 fixes hoàn tất."
echo ""
echo "  Verify:"
echo "    python -m py_compile src/littrans/ui/app.py && echo 'app.py OK'"
echo "═══════════════════════════════════════════════════════"