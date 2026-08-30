from __future__ import annotations
import platform, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main()->int:
    flutter=shutil.which("flutter")
    if not flutter:
        print("Flutter SDK is required for the Dana desktop interface.")
        print("Install Flutter, enable your desktop target, then run this command again.")
        return 1
    target={"Windows":"windows","Darwin":"macos"}.get(platform.system(),"linux")
    gui=ROOT/"gui_flutter"
    return subprocess.run([flutter,"run","-d",target],cwd=gui).returncode
if __name__=="__main__": raise SystemExit(main())
