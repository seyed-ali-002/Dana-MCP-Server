from pathlib import Path

from dana.security import path_policy


def test_empty_allowed_paths_means_all_except_denied(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed.txt"
    denied = tmp_path / "secret.txt"
    allowed.write_text("ok")
    denied.write_text("no")
    monkeypatch.setenv("DANA_ALLOWED_PATHS", "")
    monkeypatch.setenv("DANA_DENIED_PATHS", str(denied))
    assert path_policy.is_allowed(allowed)
    assert not path_policy.is_allowed(denied)


def test_allowed_paths_scope_access(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "inside.txt"
    outside = tmp_path / "outside.txt"
    monkeypatch.setenv("DANA_ALLOWED_PATHS", str(root))
    monkeypatch.setenv("DANA_DENIED_PATHS", "")
    assert path_policy.is_allowed(inside)
    assert not path_policy.is_allowed(outside)


def test_denied_paths_take_precedence(monkeypatch, tmp_path):
    root = tmp_path / "root"
    secret = root / "secret"
    secret.mkdir(parents=True)
    monkeypatch.setenv("DANA_ALLOWED_PATHS", str(root))
    monkeypatch.setenv("DANA_DENIED_PATHS", str(secret))
    assert path_policy.is_allowed(root / "public.txt")
    assert not path_policy.is_allowed(secret / "private.txt")
