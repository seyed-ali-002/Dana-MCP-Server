from pathlib import Path


def test_root_launchers_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "run.sh").is_file()
    assert (root / "run.bat").is_file()
    assert (root / "scripts" / "run.py").is_file()



def test_install_entrypoints_are_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "install.py").is_file()
    assert (root / "start.py").is_file()



def test_run_wrappers_point_to_installer():
    root = Path(__file__).resolve().parents[1]
    assert "install.py" in (root / "run.sh").read_text()
    assert "install.py" in (root / "run.bat").read_text()
    assert "install.py" in (root / "run.cmd").read_text()
    assert "install.py" in (root / "START").read_text()
    assert "install.py" in (root / "START.bat").read_text()



def test_venv_python_path():
    from dana.cli import venv_python
    assert venv_python().name in {"python", "python.exe"}



def test_ip_detection():
    from dana.cli import is_ip_address
    assert is_ip_address("127.0.0.1")
    assert not is_ip_address("mcp.example.com")



def test_installer_uses_project_venv():
    from dana.cli import install_python_dependencies
    import inspect
    source = inspect.getsource(install_python_dependencies)
    assert "ensure_venv" in source
    assert "str(python)" in source



def test_installer_entrypoint_imports():
    import install
    assert callable(install.main)






def test_install_script_does_not_install_into_system_python():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "install.py").read_text()
    assert "pip install" not in text
