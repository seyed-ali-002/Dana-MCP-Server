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


def test_root_run_wrappers_use_runner_not_installer():
    root = Path(__file__).resolve().parents[1]
    for name in ("run", "run.sh", "run.bat", "run.cmd", "START", "START.bat"):
        text = (root / name).read_text()
        assert "scripts/run.py" in text
        assert "install.py" not in text



def test_caddy_rejects_occupied_ports_when_service_is_inactive(monkeypatch):
    from dana import cli

    monkeypatch.setattr(cli, "service_is_active", lambda _name: False)
    monkeypatch.setattr(cli, "listening_ports", lambda: {443: "LISTEN 0 4096 0.0.0.0:443"})

    try:
        cli.configure_caddy("mcp.example.com")
    except RuntimeError as exc:
        assert "443" in str(exc)
        assert "already in use" in str(exc)
    else:
        raise AssertionError("Expected an occupied-port error")


def test_caddy_uses_reload_only_when_active(monkeypatch):
    from dana import cli

    commands = []
    monkeypatch.setattr(cli, "service_is_active", lambda _name: True)
    monkeypatch.setattr(cli, "listening_ports", lambda: {443: "LISTEN"})
    monkeypatch.setattr(cli, "run_command", lambda command, check=True: commands.append(command))

    cli.configure_caddy("mcp.example.com")

    assert ["sudo", "systemctl", "reload", "caddy"] in commands
    assert ["sudo", "systemctl", "start", "caddy"] not in commands
