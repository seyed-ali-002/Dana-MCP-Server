from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

def _venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=ROOT).returncode

def _bootstrap() -> int:
    py = _venv_python()
    if not py.exists():
        print("Creating Dana virtual environment (.venv)...")
        rc = _run([sys.executable, "-m", "venv", str(VENV)])
        if rc:
            print("Failed to create .venv. On Debian/Ubuntu run: sudo apt install python3-venv")
            return rc

    # Always ensure pip itself is available inside the isolated environment.
    rc = _run([str(py), "-m", "ensurepip", "--upgrade"])
    if rc:
        print("Could not initialize pip inside .venv.")
        return rc

    # Verify the actual GUI dependency with the exact interpreter that will run Dana.
    check = subprocess.run([str(py), "-c", "import PySide6; print(PySide6.__version__)"], cwd=ROOT)
    if check.returncode != 0:
        print("Installing Dana dependencies into the isolated .venv...")
        rc = _run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        if rc:
            return rc
        rc = _run([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
        if rc:
            print("Dependency installation failed; the GUI was not started.")
            return rc
        # Fail clearly here rather than later with a traceback from dana.gui.
        check = subprocess.run([str(py), "-c", "import PySide6"], cwd=ROOT)
        if check.returncode != 0:
            print("PySide6 is still unavailable inside .venv after installation.")
            return check.returncode or 1

    # Re-exec the launcher under .venv. This guarantees all imports use that environment.
    if Path(sys.prefix).resolve() != VENV.resolve():
        os.execv(str(py), [str(py), str(ROOT / "run_gui.py")])
    return 0

def main() -> int:
    rc = _bootstrap()
    if rc:
        return rc
    try:
        from dana.gui import main as gui_main
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print("PySide6 could not be loaded from the active .venv. Delete .venv and run again.")
            return 1
        raise
    return gui_main()

if __name__ == "__main__":
    raise SystemExit(main())
