"""Shared pytest fixtures.

Tests must never depend on the developer's machine. Without isolation they read
the real ``access_policy.json`` (so writes under pytest's tmp_path are denied),
query the live Tailscale node, and read the real ``.env`` for the public host.
That made results differ between a developer box and CI (SRS NFR-008).

This only isolates the *tests*; product behaviour (path policy, placeholder-host
rejection in ``dana.public_host``) is intentionally left untouched.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _isolate_host_environment(monkeypatch, tmp_path):
    from dana import public_host
    from dana.security import path_policy

    # Private policy file. It is pre-created on purpose: when CONFIG is missing,
    # load_policy() migrates a legacy config/access_policy.json from the project,
    # which would leak the developer's real allowed_paths back into the test.
    policy_file = tmp_path / "dana_test_access_policy.json"
    policy_file.write_text(json.dumps(path_policy.DEFAULT), encoding="utf-8")
    monkeypatch.setattr(path_policy, "CONFIG", policy_file)
    monkeypatch.delenv("DANA_ALLOWED_PATHS", raising=False)
    monkeypatch.delenv("DANA_DENIED_PATHS", raising=False)

    # Never query the live Tailscale node or the developer's real .env files.
    monkeypatch.setattr(public_host, "_from_funnel_status", lambda: "")
    monkeypatch.setattr(public_host, "_from_tailscale_status", lambda: "")
    monkeypatch.setattr(public_host, "_from_env_files", lambda: "")
