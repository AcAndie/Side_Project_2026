"""
scripts/run_ui.py — Khởi động LiTTrans Web UI

Cách dùng:
    python scripts/run_ui.py
    python scripts/run_ui.py --port 8502
    python scripts/run_ui.py --host 0.0.0.0 --port 8080
"""
import sys
import subprocess
from pathlib import Path


def main() -> None:
    # scripts/ nằm trong <project_root>/scripts/ → UI app ở <project_root>/src/
    project_root = Path(__file__).parent.parent
    ui_app = project_root / "src" / "littrans" / "ui" / "app.py"

    if not ui_app.exists():
        print(f"❌ Không tìm thấy: {ui_app}")
        sys.exit(1)

    # Parse --port / --host từ argv
    port = "8501"
    host = "localhost"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ("--port", "-p") and i + 1 < len(args):
            port = args[i + 1]
        if arg in ("--host", "-h") and i + 1 < len(args):
            host = args[i + 1]

    cmd = [
        sys.executable, "-m", "streamlit", "run", str(ui_app),
        "--server.port", port,
        "--server.address", host,
        "--server.headless", "false",
        "--browser.gatherUsageStats", "false",
    ]

    print(f"🚀 Khởi động LiTTrans UI tại http://{host}:{port}")
    print(f"   File: {ui_app.relative_to(Path.cwd()) if ui_app.is_relative_to(Path.cwd()) else ui_app}")
    print("   Ctrl+C để dừng.\n")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n⏹  Đã dừng.")


if __name__ == "__main__":
    main()
