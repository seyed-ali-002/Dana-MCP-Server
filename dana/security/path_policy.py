from __future__ import annotations
import json, os
from pathlib import Path
from threading import RLock

CONFIG = Path(os.getenv("DANA_ACCESS_POLICY_FILE", "config/access_policy.json")).expanduser()
_LOCK = RLock()
DEFAULT = {"version": 1, "allowed_paths": [], "deny_paths": [], "shell": {"restricted": True}, "audit_log": True}

def _norm(value: str | Path) -> Path:
    return Path(value).expanduser().resolve(strict=False)

def load_policy() -> dict:
    with _LOCK:
        if not CONFIG.exists():
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(DEFAULT, indent=2))
            return dict(DEFAULT)
        data = json.loads(CONFIG.read_text())
        out = dict(DEFAULT); out.update(data or {})
        out["shell"] = {**DEFAULT["shell"], **(data.get("shell", {}) if isinstance(data, dict) else {})}
        return out

def save_policy(policy: dict) -> dict:
    with _LOCK:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(policy, indent=2))
    return policy

def is_allowed(path: str | Path) -> bool:
    target = _norm(path); policy = load_policy()
    denied = [_norm(x) for x in policy.get("deny_paths", [])]
    if any(target == d or d in target.parents for d in denied): return False
    allowed = [_norm(x) for x in policy.get("allowed_paths", [])]
    if not allowed: return True
    return any(target == a or a in target.parents for a in allowed)

def require_path(path: str | Path, *, purpose: str = "access") -> Path:
    target = _norm(path)
    if not is_allowed(target):
        raise PermissionError(f"Dana path policy denied {purpose}: {target}")
    return target

def require_output_path(path: str | Path) -> Path:
    return require_path(path, purpose="output")

def policy_status() -> dict:
    p = load_policy(); return {"restricted": bool(p.get("allowed_paths")), "allowed_paths": p.get("allowed_paths", []), "deny_paths": p.get("deny_paths", []), "shell": p.get("shell", {}), "config": str(CONFIG.resolve())}

def set_allowed_paths(paths: list[str]) -> dict:
    p=load_policy(); p["allowed_paths"]=[str(_norm(x)) for x in paths]; save_policy(p); return policy_status()

def add_allowed_path(path: str) -> dict:
    p=load_policy(); v=str(_norm(path)); p.setdefault("allowed_paths", [])
    if v not in p["allowed_paths"]: p["allowed_paths"].append(v)
    save_policy(p); return policy_status()

def remove_allowed_path(path: str) -> dict:
    p=load_policy(); v=str(_norm(path)); p["allowed_paths"]=[x for x in p.get("allowed_paths", []) if str(_norm(x))!=v]; save_policy(p); return policy_status()
