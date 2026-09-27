from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_is_space_safe():
    text = (ROOT / "run.bat").read_text(encoding="utf-8")
    assert 'cd /d "%~dp0"' in text
    assert "scripts/run.py" in text
    assert 'py -3 scripts/run.py %*' in text
    assert 'python scripts/run.py %*' in text
    assert "install.py" not in text


def test_runner_has_windows_interpreter_fallback():
    text = (ROOT / "scripts/run.py").read_text(encoding="utf-8")
    assert "python_command" in text
    assert '("py", "-3")' in text
    assert '("python",)' in text


def test_single_command_start_flow_includes_funnel():
    text = (ROOT / "dana/cli.py").read_text(encoding="utf-8")
    assert 'command in {"run", "start-all", "up"}' in text
    assert "_docker_install()" in text
    assert "_docker_connect()" in text
