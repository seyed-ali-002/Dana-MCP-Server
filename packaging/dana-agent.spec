from pathlib import Path
from PyInstaller.utils.hooks import collect_all

SPEC_PATH = Path("packaging/dana-agent.spec").resolve()
ROOT = SPEC_PATH.parents[1]
datas, binaries, hiddenimports = collect_all("dana")

a = Analysis(
    [str(ROOT / "dana" / "setup_service.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
)
