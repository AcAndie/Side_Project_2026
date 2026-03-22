"""
scripts/reset.py — Dọn dẹp hệ thống về trạng thái ban đầu.

Modes:
    python scripts/reset.py          — xóa outputs + logs + staging data
    python scripts/reset.py --full   — xóa toàn bộ data (bao gồm glossary, characters, bible)
    python scripts/reset.py --list   — chỉ liệt kê những gì sẽ bị xóa

CẢNH BÁO: --full không thể phục hồi nếu không có backup.
"""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

# Đảm bảo import được từ src/
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))


_SAFE_TARGETS = [
    ("outputs/",        "Bản dịch (*_VN.txt)"),
    ("logs/",           "Log files"),
    ("data/glossary/Staging_Terms*.md",    "Glossary staging"),
    ("data/characters/Staging_Characters.json", "Character staging"),
    ("data/bible/staging/", "Bible staging"),
    ("data/name_fixes.json", "Name fixes log"),
]

_FULL_TARGETS = [
    ("data/glossary/",   "Toàn bộ Glossary (Pathways, Organizations, Items, Locations, General)"),
    ("data/characters/", "Toàn bộ Character profiles (Active, Archive)"),
    ("data/skills/",     "Skills database"),
    ("data/memory/",     "Arc Memory & Context Notes"),
    ("data/bible/",      "Bible System (database, worldbuilding, main_lore)"),
]


def _collect(targets: list[tuple[str, str]], root: Path) -> list[tuple[Path, str]]:
    result = []
    for pattern, label in targets:
        if "*" in pattern:
            for p in root.glob(pattern):
                result.append((p, label))
        else:
            p = root / pattern
            if p.exists():
                result.append((p, label))
    return result


def _delete(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)   # recreate thư mục rỗng
    elif path.is_file():
        path.unlink()


def main() -> None:
    args = sys.argv[1:]
    full = "--full" in args
    list_only = "--list" in args or "-l" in args

    root = _ROOT
    targets = _collect(_SAFE_TARGETS, root)
    if full:
        targets += _collect(_FULL_TARGETS, root)

    if not targets:
        print("✅ Không có gì để dọn dẹp.")
        return

    mode_label = "FULL RESET" if full else "Safe reset (chỉ outputs + staging)"
    print(f"\n{'═'*60}")
    print(f"  LiTTrans — {mode_label}")
    print(f"{'═'*60}\n")
    print("  Sẽ xóa:")
    for path, label in targets:
        size = ""
        if path.is_dir():
            n = sum(1 for _ in path.rglob("*") if _.is_file())
            size = f"  ({n} files)"
        print(f"    • {path.relative_to(root)}  — {label}{size}")

    if list_only:
        print("\n  [--list mode] Không thực hiện xóa.")
        return

    if full:
        print("\n  ⚠️  CẢNH BÁO: --full sẽ xóa toàn bộ data đã tích lũy!")
        confirm = input("  Gõ 'YES' để xác nhận: ").strip()
        if confirm != "YES":
            print("  Huỷ.")
            return
    else:
        confirm = input("\n  Xác nhận xóa? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Huỷ.")
            return

    print()
    for path, label in targets:
        try:
            _delete(path)
            print(f"  🗑️  {path.relative_to(root)}")
        except Exception as e:
            print(f"  ❌ Lỗi khi xóa {path}: {e}")

    print(f"\n✅ Dọn dẹp xong ({mode_label}).\n")


if __name__ == "__main__":
    main()
