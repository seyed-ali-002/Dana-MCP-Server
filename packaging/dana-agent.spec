# Lean Dana desktop sidecar.
# - collect_submodules(dana) instead of collect_all (avoids packing every data file)
# - Playwright / pytest / ruff / mypy / pip-audit excluded (optional extras)
# - Document + token + rich stacks stay available for core tools
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_PATH = Path("packaging/dana-agent.spec").resolve()
ROOT = SPEC_PATH.parents[1]

hiddenimports = collect_submodules("dana")
datas = collect_data_files("certifi")
binaries = []

for pkg in ("docx", "reportlab", "arabic_reshaper", "bidi", "pypdf", "tiktoken", "rich"):
    try:
        datas += collect_data_files(pkg)
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

EXCLUDES = [
    "pytest",
    "pytest_cov",
    "_pytest",
    "py",
    "pluggy",
    "ruff",
    "mypy",
    "mypy.*",
    "playwright",
    "playwright.*",
    "greenlet",
    "pip_audit",
    "pip_audit.*",
    "tkinter",
    "turtle",
    "test",
    "tests",
    "unittest",
    "pydoc",
    "doctest",
]

a = Analysis(
    [str(ROOT / "dana" / "setup_service.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=EXCLUDES,
    noarchive=False,
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
    upx=True,
    upx_exclude=[],
    strip=True,
)
