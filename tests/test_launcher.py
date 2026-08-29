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



def test_server_uses_public_port_in_environment(tmp_path, monkeypatch):
    from dana import cli

    monkeypatch.setattr(cli, "ROOT", tmp_path)
    cli.write_env("server", "mcp.example.com", 18080)
    text = (tmp_path / ".env").read_text()
    assert "DANA_HOST=127.0.0.1" in text
    assert "DANA_PORT=18080" in text
    assert "DANA_PUBLIC_PORT=0" in text
    assert "DANA_PUBLIC_SCHEME=https" in text


def test_port_is_listening_can_be_mocked_for_selection(monkeypatch):
    from dana import cli

    monkeypatch.setattr(cli, "port_is_listening", lambda port: port == 18080)
    assert cli.port_is_listening(18080)
    assert not cli.port_is_listening(18081)



def test_server_proxy_is_loopback_only():
    from dana import cli
    import inspect

    source = inspect.getsource(cli.write_env)
    assert 'values["DANA_HOST"] = "127.0.0.1"' in source


def test_server_connector_uses_https_proxy_url():
    from dana import cli
    import inspect

    source = inspect.getsource(cli.install_server)
    assert 'connector_url = f"https://{host}/mcp"' in source
    assert "configure_reverse_proxy(host, public_port)" in source
