from __future__ import annotations

import subprocess
from pathlib import Path

from dana import container


def test_compose_file_exists_and_is_persistent():
    assert container.COMPOSE_FILE.is_file()
    text = container.COMPOSE_FILE.read_text(encoding="utf-8")
    assert "restart: unless-stopped" in text
    assert "dana_runtime:/data/dana" in text
    assert "127.0.0.1:8765:8765" in text
    assert "no-new-privileges:true" in text
    assert "cap_drop:" in text


def test_docker_command_requires_compose_v2(monkeypatch):
    monkeypatch.setattr(container.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)

    class Result:
        returncode = 0
        stdout = "Docker Compose version v2.30.0"
        stderr = ""

    monkeypatch.setattr(container.subprocess, "run", lambda *args, **kwargs: Result())
    assert container.docker_command() == ["docker", "compose"]


def test_docker_command_fails_cleanly_without_docker(monkeypatch):
    monkeypatch.setattr(container.shutil, "which", lambda name: None)
    try:
        container.docker_command()
    except container.DockerUnavailable as exc:
        assert "Docker is not installed" in str(exc)
    else:
        raise AssertionError("DockerUnavailable was not raised")


def test_compose_args_uses_project_file(monkeypatch):
    monkeypatch.setattr(container, "docker_command", lambda: ["docker", "compose"])
    args = container.compose_args("ps")
    assert args[:5] == ["docker", "compose", "-p", "dana", "-f"]
    assert args[-1] == "ps"


def test_compose_does_not_use_shell(monkeypatch):
    calls = []

    monkeypatch.setattr(container, "compose_args", lambda *args: ["docker", "compose", *args])

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(container.subprocess, "run", fake_run)
    container.compose("ps")

    assert calls
    assert calls[0][1]["cwd"] == container.ROOT
    assert calls[0][1]["text"] is True
    assert calls[0][1]["check"] is True
