from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

CONFIG = Path(os.getenv("DANA_ACCESS_POLICY_FILE", "config/access_policy.json")).expanduser()
_LOCK = RLock()
DEFAULT = {
    "version": 1,
    "allowed_paths": [],
    "deny_paths": [],
    "shell": {"restricted": True},
    "audit_log": True,
}


def _norm(value: str | Path) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _clean_path_list(values: object) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for item in values:  # type: ignore[union-attr]
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _env_paths(key: str) -> list[str]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return _clean_path_list(parsed)
    except json.JSONDecodeError:
        pass
    return _clean_path_list(raw.replace("\r", "").replace(",", "\n").split("\n"))


def load_policy() -> dict:
    with _LOCK:
        if not CONFIG.exists():
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(DEFAULT, indent=2))
            return dict(DEFAULT)
        data = json.loads(CONFIG.read_text())
        out = dict(DEFAULT)
        out.update(data or {})
        out["shell"] = {
            **DEFAULT["shell"],
            **(data.get("shell", {}) if isinstance(data, dict) else {}),
        }
        out["allowed_paths"] = _clean_path_list(out.get("allowed_paths"))
        out["deny_paths"] = _clean_path_list(out.get("deny_paths") or out.get("denied_paths"))
        # Env overrides when the variable is present (even if empty → unrestricted).
        if "DANA_ALLOWED_PATHS" in os.environ:
            out["allowed_paths"] = _env_paths("DANA_ALLOWED_PATHS")
        if "DANA_DENIED_PATHS" in os.environ:
            out["deny_paths"] = _env_paths("DANA_DENIED_PATHS")
        return out


def save_policy(policy: dict) -> dict:
    with _LOCK:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(policy, indent=2))
        return policy


def is_allowed(path: str | Path) -> bool:
    """Empty allowed_paths means unrestricted (still respects deny_paths)."""
    target = _norm(path)
    policy = load_policy()
    denied = [_norm(x) for x in policy.get("deny_paths", [])]
    if any(target == d or d in target.parents for d in denied):
        return False
    allowed = [_norm(x) for x in policy.get("allowed_paths", [])]
    if not allowed:
        return True
    return any(target == a or a in target.parents for a in allowed)


def resolve_user_path(path: str | Path) -> Path:
    """Resolve relative tool paths against allowed roots, then cwd/home.

    When allowed_paths is non-empty, prefer roots from that list so relative
    names like "config" resolve inside the project even if process cwd differs.
    """
    raw = Path(str(path)).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)

    policy = load_policy()
    allowed_roots = [_norm(x) for x in policy.get("allowed_paths", [])]
    under_allowed = [(root / raw).resolve(strict=False) for root in allowed_roots]
    cwd_c = (Path.cwd() / raw).resolve(strict=False)
    home_c = (Path.home() / raw).resolve(strict=False)

    for c in under_allowed + [cwd_c, home_c]:
        if c.exists() and is_allowed(c):
            return c
    for c in under_allowed:
        if is_allowed(c):
            return c
    if is_allowed(cwd_c):
        return cwd_c
    if is_allowed(home_c):
        return home_c
    if under_allowed:
        return under_allowed[0]
    return cwd_c


def require_path(path: str | Path, *, purpose: str = "access") -> Path:
    target = resolve_user_path(path)
    if not is_allowed(target):
        policy = load_policy()
        allowed = policy.get("allowed_paths") or []
        if allowed:
            raise PermissionError(
                f"Dana path policy denied {purpose}: {target}. "
                f"Path is outside allowed_paths ({len(allowed)} root(s)). "
                f"Clear allowed_paths for full access, or add this root."
            )
        raise PermissionError(f"Dana path policy denied {purpose}: {target}")
    return target


def require_output_path(path: str | Path) -> Path:
    return require_path(path, purpose="output")


def policy_status() -> dict:
    p = load_policy()
    allowed = p.get("allowed_paths", [])
    return {
        "restricted": bool(allowed),
        "unrestricted": not bool(allowed),
        "allowed_paths": allowed,
        "deny_paths": p.get("deny_paths", []),
        "shell": p.get("shell", {}),
        "config": str(CONFIG.resolve()),
        "note": (
            "allowed_paths is empty → all filesystem paths are allowed except deny_paths."
            if not allowed
            else "Access is limited to allowed_paths (and blocked by deny_paths)."
        ),
    }


def set_allowed_paths(paths: list[str]) -> dict:
    p = load_policy()
    p["allowed_paths"] = [str(_norm(x)) for x in _clean_path_list(paths)]
    save_policy(p)
    return policy_status()


def add_allowed_path(path: str) -> dict:
    p = load_policy()
    v = str(_norm(path))
    p.setdefault("allowed_paths", [])
    if v not in p["allowed_paths"]:
        p["allowed_paths"].append(v)
    save_policy(p)
    return policy_status()


def remove_allowed_path(path: str) -> dict:
    p = load_policy()
    v = str(_norm(path))
    p["allowed_paths"] = [x for x in p.get("allowed_paths", []) if str(_norm(x)) != v]
    save_policy(p)
    return policy_status()
