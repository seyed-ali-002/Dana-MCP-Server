from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

def _venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def _ensure_venv() -> int:
    py = _venv_python()
    if not py.exists():
        print("Creating project virtual environment (.venv)...")
        result = subprocess.run([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT)
        if result.returncode != 0:
            print("Could not create .venv. On Debian/Ubuntu install the venv package, e.g.:")
            print("  sudo apt install python3-venv")
            return result.returncode or 1
    try:
        subprocess.run([str(py), "-c", "import PySide6"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Installing Dana GUI dependencies into .venv...")
        result = subprocess.run([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], cwd=ROOT)
        if result.returncode != 0:
            return result.returncode
    # Re-launch with the isolated interpreter so imports always use .venv.
    if Path(sys.executable).resolve() != py.resolve():
        return subprocess.run([str(py), str(ROOT / "run_gui.py")], cwd=ROOT).returncode
    return -1

def main() -> int:
    status = _ensure_venv()
    if status >= 0:
        return status
    from dana.gui import main as gui_main
    return gui_main()

if __name__ == "__main__":
    raise SystemExit(main())
