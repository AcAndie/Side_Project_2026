"""
scripts/main.py — Entry point duy nhất cho toàn bộ pipeline.

Cách dùng:
    python scripts/main.py translate
    python scripts/main.py retranslate [KEYWORD]
    python scripts/main.py clean glossary
    python scripts/main.py clean characters [--action merge|review|...]
    python scripts/main.py fix-names [--list] [--dry-run]
    python scripts/main.py --help
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

# scripts/ nằm 1 cấp dưới project root → cần thêm cả root và src/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)

from littrans.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
