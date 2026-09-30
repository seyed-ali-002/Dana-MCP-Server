import os

import pytest

from dana.tools import local_agent


def test_desktop_backend_prefers_ydotool_on_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else None)
    assert local_agent._desktop_backend() == "ydotool"


def test_desktop_backend_uses_xdotool_on_x11(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/xdotool" if name == "xdotool" else None)
    assert local_agent._desktop_backend() == "xdotool"


def test_wayland_without_ydotool_fails_with_actionable_error(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Wayland desktop control requires ydotool"):
        local_agent._desktop_backend()


def test_default_screenshot_path_is_not_project_root(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: None)
    path = local_agent._store("screenshots/dana-screenshot.png")
    assert os.path.expanduser("~/.config/dana") in str(path)


def test_ydotool_legacy_variant(monkeypatch):
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else None)
    class Result:
        stdout = "Usage: ydotool <cmd> <args>\\nAvailable commands:\\n  recorder\\n  mousemove\\n  key\\n  click\\n"
        stderr = ""
    monkeypatch.setattr(local_agent.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(local_agent, "_YDOTOOL_VARIANT", None)
    assert local_agent._ydotool_variant() == "legacy"


def test_ydotool_modern_variant(monkeypatch):
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else None)
    class Result:
        stdout = "Available commands:\\n  click\\n  mousemove\\n  type\\n  key\\n  debug\\n  stdin\\n"
        stderr = ""
    monkeypatch.setattr(local_agent.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(local_agent, "_YDOTOOL_VARIANT", None)
    assert local_agent._ydotool_variant() == "modern"


def test_ydotool_legacy_move_uses_legacy_syntax(monkeypatch):
    calls = []
    monkeypatch.setattr(local_agent, "_YDOTOOL_VARIANT", "legacy")
    monkeypatch.setattr(local_agent, "_ydotool_uinput_error", lambda: None)
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: None)
    monkeypatch.setattr(local_agent.subprocess, "run", lambda cmd, **kwargs: calls.append(cmd) or type("R", (), {"returncode":0,"stdout":"","stderr":""})())
    result = local_agent._desktop_ydo("move", 1400, 750)
    assert result["ok"] is True
    assert calls == [["ydotool", "mousemove", "1400", "750"]]



def test_ydotool_stderr_failure_is_not_success(monkeypatch):
    monkeypatch.setattr(local_agent, "_YDOTOOL_VARIANT", "modern")
    monkeypatch.setattr(local_agent, "_ydotool_uinput_error", lambda: None)
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else None)
    monkeypatch.setattr(local_agent.subprocess, "run", lambda cmd, **kwargs: type("R", (), {"returncode":0,"stdout":"","stderr":"ydotoold backend unavailable"})())
    result = local_agent._desktop_ydo("move", 10, 20)
    assert result["ok"] is False
    assert "backend unavailable" in result["error"]


def test_desktop_diagnostics_reports_uinput_failure(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else ("/usr/bin/ydotoold" if name == "ydotoold" else None))
    monkeypatch.setattr(local_agent, "_ydotool_variant", lambda: "legacy")
    monkeypatch.setattr(local_agent, "_ydotool_uinput_error", lambda: "uinput unavailable")
    result = local_agent._desktop_diagnostics()
    assert result["ok"] is False
    assert result["error"] == "uinput unavailable"


def test_legacy_ydotool_uses_legacy_absolute_and_relative_syntax(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(local_agent, "_ydotool_variant", lambda: "legacy")
    monkeypatch.setattr(local_agent, "_ydotool_uinput_error", lambda: None)
    monkeypatch.setattr(local_agent, "_ydotool_socket_available", lambda: True)
    monkeypatch.setattr(local_agent, "_ydotool_socket_path", lambda: "/tmp/.ydotool_socket")
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name in {"ydotool","ydotoold"} else None)
    commands = []
    monkeypatch.setattr(local_agent, "_run", lambda cmd, timeout=30, **kwargs: commands.append(cmd) or {"command":cmd,"returncode":0,"stdout":"","stderr":"","ok":True})
    assert local_agent._desktop_ydo("move", 1400, 750)["ok"]
    assert local_agent._desktop_ydo("move_relative", 10, -5)["ok"]
    assert commands[0] == ["ydotool", "mousemove", "1400", "750"]
    assert commands[1] == ["ydotool", "mousemove_relative", "--", "10", "-5"]


def test_ydotool_nonzero_stderr_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(local_agent, "_ydotool_variant", lambda: "legacy")
    monkeypatch.setattr(local_agent, "_ydotool_uinput_error", lambda: None)
    monkeypatch.setattr(local_agent, "_ydotool_socket_available", lambda: True)
    monkeypatch.setattr(local_agent, "_ydotool_socket_path", lambda: "/tmp/.ydotool_socket")
    monkeypatch.setattr(local_agent.shutil, "which", lambda name: "/usr/bin/ydotool" if name == "ydotool" else None)
    monkeypatch.setattr(
        local_agent,
        "_run",
        lambda cmd, timeout=30, **kwargs: {"command":cmd,"returncode":0,"stdout":"","stderr":"ydotool: error: failed to open uinput device","ok":True},
    )
    result = local_agent._desktop_ydo("move", 10, 20)
    assert result["ok"] is False
    assert "failed to open uinput device" in result["error"]



def test_ydotool_legacy_scroll_uses_wheel_click(monkeypatch):
    monkeypatch.setattr(local_agent, "_YDOTOOL_VARIANT", "legacy")
    monkeypatch.setattr(local_agent, "_ydotool_uinput_error", lambda: None)
    calls = []
    monkeypatch.setattr(local_agent, "_run", lambda cmd, timeout=30, **kwargs: calls.append(cmd) or {"command":cmd,"returncode":0,"stdout":"","stderr":"","ok":True})
    result = local_agent._desktop_ydo("scroll", scroll=3)
    assert result["ok"] is True
    assert calls == [["ydotool", "click", "--repeat", "3", "4"]]
