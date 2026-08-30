from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main() -> int:
    try:
        from PySide6 import QtWidgets  # noqa: F401
    except ModuleNotFoundError:
        print("PySide6 is not installed for this Python interpreter.")
        print(f"Installing it with: {sys.executable} -m pip install -r requirements.txt")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], cwd=ROOT)
        if result.returncode != 0:
            print("Automatic installation failed. Activate the project virtual environment and install requirements.txt manually.")
            return result.returncode
    from dana.gui import main as gui_main
    return gui_main()

if __name__ == "__main__":
    raise SystemExit(main())
