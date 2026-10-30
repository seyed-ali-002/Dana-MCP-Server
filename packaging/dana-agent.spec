from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_PATH = Path("packaging/dana-agent.spec").resolve()
ROOT = SPEC_PATH.parents[1]

# Keep Dana's Python modules available for runtime/plugin discovery, but do not
# blindly collect every package data file and binary from the whole package.
hiddenimports = collect_submodules("dana")
datas = collect_data_files("certifi")

a = Analysis(
    [str(ROOT / "dana" / "setup_service.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "pytest",
        "pytest_cov",
        "ruff",
        "mypy",
        "pip_audit",
    ],
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="dana-agent",
    console=True,
    strip=True,
)
