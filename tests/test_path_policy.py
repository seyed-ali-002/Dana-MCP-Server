from pathlib import Path

from dana.security import path_policy


def _isolate(monkeypatch, tmp_path):
    policy_file = tmp_path / "access_policy.json"
    monkeypatch.setattr(path_policy, "CONFIG", policy_file)
    monkeypatch.delenv("DANA_ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("DANA_DENIED_PATHS", raising=False)


def test_empty_allowed_paths_means_all_except_denied(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    allowed = tmp_path / "allowed.txt"
    denied = tmp_path / "secret.txt"
    allowed.write_text("ok")
    denied.write_text("no")
    path_policy.save_policy(
        {"version": 1, "allowed_paths": [], "deny_paths": [str(denied)], "shell": {"restricted": True}}
    )
    assert path_policy.is_allowed(allowed)
    assert not path_policy.is_allowed(denied)


def test_allowed_paths_scope_access(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "inside.txt"
    outside = tmp_path / "outside.txt"
    path_policy.save_policy(
        {"version": 1, "allowed_paths": [str(root)], "deny_paths": [], "shell": {"restricted": True}}
    )
    assert path_policy.is_allowed(inside)
    assert not path_policy.is_allowed(outside)


def test_denied_paths_take_precedence(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "root"
    secret = root / "secret"
    secret.mkdir(parents=True)
    path_policy.save_policy(
        {
            "version": 1,
            "allowed_paths": [str(root)],
            "deny_paths": [str(secret)],
            "shell": {"restricted": True},
        }
    )
    assert path_policy.is_allowed(root / "public.txt")
    assert not path_policy.is_allowed(secret / "private.txt")


def test_relative_path_resolves_under_allowed_root(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    root = tmp_path / "project"
    cfg = root / "config"
    cfg.mkdir(parents=True)
    (cfg / "a.txt").write_text("x")
    path_policy.save_policy(
        {"version": 1, "allowed_paths": [str(root)], "deny_paths": [], "shell": {"restricted": True}}
    )
    monkeypatch.chdir(tmp_path)  # cwd outside project
    resolved = path_policy.resolve_user_path("config")
    assert resolved == cfg.resolve()
    assert path_policy.is_allowed(resolved)


def test_env_empty_allowed_overrides_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    path_policy.save_policy(
        {"version": 1, "allowed_paths": [str(tmp_path / "only")], "deny_paths": [], "shell": {}}
    )
    monkeypatch.setenv("DANA_ALLOWED_PATHS", "")
    assert path_policy.load_policy()["allowed_paths"] == []
    assert path_policy.is_allowed(tmp_path / "anywhere.txt")
