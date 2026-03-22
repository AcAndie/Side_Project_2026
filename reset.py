"""
reset.py (project root) — Redirect wrapper.

Script reset thực tế nằm ở scripts/reset.py.
File này chỉ là entry point tiện lợi để gọi từ root.

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