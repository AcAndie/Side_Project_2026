#!/bin/bash
# INSTALL.sh — Script hoàn tất Đại Tu
# Chạy từ project root: bash INSTALL.sh
set -e

echo "=== LiTTrans Đại Tu — Bước 2: Copy file gốc ==="
echo ""

REQUIRED=(
  "src/littrans/engine/pre_processor.py"
  "src/littrans/engine/post_analyzer.py"
  "src/littrans/engine/quality_guard.py"
  "src/littrans/utils/text_normalizer.py"
  "src/littrans/utils/post_processor.py"
  "src/littrans/managers/base.py"
  "src/littrans/managers/glossary.py"
  "src/littrans/managers/characters.py"
  "src/littrans/managers/name_lock.py"
  "src/littrans/managers/memory.py"
  "src/littrans/bible/schemas.py"
  "src/littrans/tools/fix_names.py"
  "src/littrans/tools/clean_glossary.py"
  "src/littrans/tools/clean_characters.py"
  "src/littrans/llm/client.py"
  "src/littrans/llm/schemas.py"
  "src/littrans/llm/token_budget.py"
  "src/littrans/llm/__init__.py"
  "src/littrans/config/settings.py"
  "src/littrans/config/__init__.py"
  "src/littrans/utils/io_utils.py"
  "src/littrans/utils/data_versioning.py"
  "src/littrans/utils/env_utils.py"
  "src/littrans/utils/logger.py"
  "src/littrans/__init__.py"
  "src/littrans/ui/app.py"
  "prompts/system_agent.md"
  "prompts/character_profile.md"
  "prompts/bible_scan.md"
  ".env.example"
  "pyproject.toml"
  "requirements.txt"
)

# Kiểm tra file nguồn tồn tại
MISSING=0
for f in "${REQUIRED[@]}"; do
  if [ ! -f "$f" ]; then
    echo "  ❌ Thiếu: $f"
    MISSING=$((MISSING + 1))
  fi
done

if [ $MISSING -gt 0 ]; then
  echo ""
  echo "❌ $MISSING file nguồn không tìm thấy. Chạy script này từ project root cũ."
  exit 1
fi

echo "✅ Tất cả file nguồn có mặt"
echo ""

# ── core/ ─────────────────────────────────────────────────────────
echo "── Bước 1: engine/ → core/ ──────────────────────────────────"
cp src/littrans/engine/pre_processor.py   src/littrans/core/pre_processor.py
cp src/littrans/engine/post_analyzer.py   src/littrans/core/post_analyzer.py
cp src/littrans/engine/quality_guard.py   src/littrans/core/quality_guard.py
cp src/littrans/utils/text_normalizer.py  src/littrans/core/text_normalizer.py
cp src/littrans/utils/post_processor.py   src/littrans/core/post_processor.py
echo "  ✓ core/ hoàn chỉnh"

# ── context/ ──────────────────────────────────────────────────────
echo ""
echo "── Bước 2: managers/ + bible/ → context/ ────────────────────"
cp src/littrans/managers/base.py       src/littrans/context/base.py
cp src/littrans/managers/glossary.py   src/littrans/context/glossary.py
cp src/littrans/managers/characters.py src/littrans/context/characters.py
cp src/littrans/managers/name_lock.py  src/littrans/context/name_lock.py
cp src/littrans/managers/memory.py     src/littrans/context/memory.py
# schemas.py đã có trong zip (không thay đổi gì)
echo "  ✓ context/ hoàn chỉnh"

# ── cli/ ──────────────────────────────────────────────────────────
echo ""
echo "── Bước 3: tools/ → cli/ ────────────────────────────────────"
cp src/littrans/tools/fix_names.py        src/littrans/cli/tool_fix.py
cp src/littrans/tools/clean_glossary.py   src/littrans/cli/tool_clean_glossary.py
cp src/littrans/tools/clean_characters.py src/littrans/cli/tool_clean_chars.py
echo "  ✓ cli/ tools hoàn chỉnh"

# ── llm/, config/, utils/ ─────────────────────────────────────────
echo ""
echo "── Bước 4: Copy llm/, config/, utils/, prompts/ ─────────────"
cp src/littrans/llm/client.py      src/littrans/llm/
cp src/littrans/llm/schemas.py     src/littrans/llm/
cp src/littrans/llm/token_budget.py src/littrans/llm/
cp src/littrans/llm/__init__.py    src/littrans/llm/
cp src/littrans/config/settings.py  src/littrans/config/
cp src/littrans/config/__init__.py  src/littrans/config/
cp src/littrans/utils/io_utils.py        src/littrans/utils/
cp src/littrans/utils/data_versioning.py src/littrans/utils/
cp src/littrans/utils/env_utils.py       src/littrans/utils/
cp src/littrans/utils/logger.py          src/littrans/utils/
cp src/littrans/__init__.py src/littrans/
cp src/littrans/ui/app.py   src/littrans/ui/
cp prompts/system_agent.md    prompts/
cp prompts/character_profile.md prompts/
cp prompts/bible_scan.md       prompts/
cp .env.example .
cp pyproject.toml .
cp requirements.txt .
echo "  ✓ Tất cả file phụ hoàn chỉnh"

# ── Patch ui/app.py imports ───────────────────────────────────────
echo ""
echo "── Bước 5: Patch ui/app.py imports ──────────────────────────"
python3 - << 'PYEOF'
p = 'src/littrans/ui/app.py'
t = open(p, encoding='utf-8').read()
subs = [
    ('from littrans.managers.characters import', 'from littrans.context.characters import'),
    ('from littrans.managers.glossary   import', 'from littrans.context.glossary   import'),
    ('from littrans.managers.glossary import',   'from littrans.context.glossary import'),
    ('from littrans.managers.skills',            'from littrans.context.skills'),
    ('from littrans.managers.name_lock',         'from littrans.context.name_lock'),
    ('from littrans.engine.pipeline',            'from littrans.core.pipeline'),
    ('from littrans.engine.scout',               'from littrans.core.scout'),
    ('from littrans.tools.clean_glossary',       'from littrans.cli.tool_clean_glossary'),
    ('from littrans.tools.clean_characters',     'from littrans.cli.tool_clean_chars'),
    ('from littrans.ui.bible_ui import render_bible_tab', 'from littrans.ui.bible_ui import render_bible_tab'),
]
changed = 0
for old, new in subs:
    if old in t:
        t = t.replace(old, new)
        changed += 1
open(p, 'w', encoding='utf-8').write(t)
print(f'  ✓ ui/app.py: {changed} imports updated')
PYEOF

# ── Xóa thư mục cũ ───────────────────────────────────────────────
echo ""
echo "── Bước 6: Dọn dẹp cấu trúc cũ ─────────────────────────────"
read -p "  Xóa engine/, managers/, bible/, tools/, cli.py gốc? [y/N]: " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
  rm -rf src/littrans/engine
  rm -rf src/littrans/managers
  rm -rf src/littrans/bible
  rm -rf src/littrans/tools
  rm -f  src/littrans/cli.py
  echo "  ✓ Dọn dẹp xong"
else
  echo "  ⏭  Bỏ qua — bạn có thể xóa thủ công sau"
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ Đại Tu hoàn tất!"
echo ""
echo "  Test ngay:"
echo "    python scripts/main.py stats"
echo "    python scripts/run_ui.py"
echo "═══════════════════════════════════════════════════"
