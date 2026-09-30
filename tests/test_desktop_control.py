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
