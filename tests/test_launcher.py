from pathlib import Path


def test_root_launchers_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "run.sh").is_file()
    assert (root / "run.bat").is_file()
    assert (root / "scripts" / "run.py").is_file()
