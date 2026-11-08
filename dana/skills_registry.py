"""Dana skills registry — load, list, enable, and import markdown skill packs."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from .subprocess_env import clean_subprocess_env
import tempfile
from pathlib import Path
from threading import RLock

_LOCK = RLock()

KNOWN_PACKS = {
    "agency-agents": {
        "url": "https://github.com/msitarzewski/agency-agents.git",
        "globs": ["**/*.md"],
        "max_files": 40,
    },
    "superpowers": {
        "url": "https://github.com/obra/superpowers.git",
        "globs": ["**/*.md", "**/skills/**/*.md"],
        "max_files": 40,
    },
    "i-have-adhd": {
        "url": "https://github.com/ayghri/i-have-adhd.git",
        "globs": ["**/*.md"],
        "max_files": 20,
    },
    "ponytail": {
        "url": "https://github.com/DietrichGebert/ponytail.git",
        "globs": ["**/*.md", "**/SKILL.md"],
        "max_files": 20,
    },
}


def _user_skills_dir() -> Path:
    base = Path.home() / ".config" / "dana" / "skills"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _project_skills_dir() -> Path:
    return Path.cwd() / "skills"


def _bundled_dir() -> Path:
    return Path(__file__).resolve().parent / "skill_packs"


def _registry_file() -> Path:
    path = Path.home() / ".config" / "dana" / "skills_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_registry() -> dict:
    path = _registry_file()
    if not path.exists():
        return {"extra_paths": [], "enabled": None, "disabled": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"extra_paths": [], "enabled": None, "disabled": []}
    data.setdefault("extra_paths", [])
    data.setdefault("disabled", [])
    # enabled: None => all on (except disabled); list => explicit allow-list
    if "enabled" not in data:
        data["enabled"] = None
    return data


def _save_registry(data: dict) -> None:
    _registry_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _iter_skill_files() -> list[Path]:
    roots: list[Path] = [_bundled_dir(), _user_skills_dir(), _project_skills_dir()]
    reg = _load_registry()
    for raw in reg.get("extra_paths", []):
        roots.append(Path(str(raw)).expanduser())
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for pattern in ("*.md", "*.txt", "*.skill.md"):
                candidates.extend(root.rglob(pattern))
        for path in sorted(candidates):
            if not path.is_file():
                continue
            # skip huge docs / license noise from imported packs
            name = path.name.lower()
            if name in {"license.md", "changelog.md", "contributing.md", "code_of_conduct.md"}:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            files.append(path)
    return files


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
            body = parts[2].lstrip("\n")
    return meta, body


def _is_enabled(skill_id: str, stem: str, reg: dict) -> bool:
    disabled = {str(x) for x in (reg.get("disabled") or [])}
    if skill_id in disabled or stem in disabled:
        return False
    enabled = reg.get("enabled")
    if enabled is None or enabled == []:
        # empty explicit list after first toggle may mean "use disabled only"
        # Convention: enabled is None => all on; enabled is list => only those
        if enabled == [] and reg.get("_explicit_enable_mode"):
            return False
        if enabled is None:
            return True
        return True  # empty without explicit mode => all on
    allow = {str(x) for x in enabled}
    return skill_id in allow or stem in allow


def list_skills() -> dict:
    items = []
    reg = _load_registry()
    for path in _iter_skill_files():
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            items.append({"id": path.stem, "path": str(path), "error": str(exc), "enabled": False})
            continue
        meta, body = _parse_frontmatter(raw)
        skill_id = meta.get("id") or path.stem
        items.append({
            "id": skill_id,
            "name": meta.get("name") or skill_id.replace("-", " ").title(),
            "description": (
                meta.get("description")
                or (body.strip().splitlines()[0][:160] if body.strip() else "")
            ),
            "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
            "path": str(path),
            "enabled": _is_enabled(skill_id, path.stem, reg),
            "chars": len(body),
            "bundled": str(_bundled_dir()) in str(path),
        })
    return {
        "ok": True,
        "count": len(items),
        "skills": items,
        "extra_paths": reg.get("extra_paths", []),
        "disabled": reg.get("disabled", []),
        "known_packs": list(KNOWN_PACKS.keys()),
    }


def get_skill(skill_id: str) -> dict:
    skill_id = (skill_id or "").strip()
    for path in _iter_skill_files():
        raw = path.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(raw)
        sid = meta.get("id") or path.stem
        if sid == skill_id or path.stem == skill_id:
            return {
                "ok": True,
                "id": sid,
                "name": meta.get("name") or sid,
                "meta": meta,
                "path": str(path),
                "content": body,
            }
    return {"ok": False, "message": f"Skill not found: {skill_id}"}


def set_skill_enabled(skill_id: str, enabled: bool) -> dict:
    skill_id = (skill_id or "").strip()
    if not skill_id:
        return {"ok": False, "message": "skill_id required"}
    with _LOCK:
        reg = _load_registry()
        disabled = [str(x) for x in (reg.get("disabled") or []) if str(x) != skill_id]
        if not enabled:
            disabled.append(skill_id)
        reg["disabled"] = disabled
        # Keep enabled as None (all-on minus disabled) for simple UX
        reg["enabled"] = None
        _save_registry(reg)
    return {"ok": True, "id": skill_id, "enabled": enabled, **list_skills()}


def add_skill_path(path: str) -> dict:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return {"ok": False, "message": f"Path does not exist: {target}"}
    with _LOCK:
        reg = _load_registry()
        paths = [str(p) for p in reg.get("extra_paths", [])]
        key = str(target)
        if key not in paths:
            paths.append(key)
        reg["extra_paths"] = paths
        _save_registry(reg)
    return {"ok": True, "path": key, **list_skills()}


def install_skill_text(name: str, content: str) -> dict:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "skill").strip()) or "skill"
    dest = _user_skills_dir() / f"{safe}.md"
    body = content if content.lstrip().startswith("---") else (
        f"---\nid: {safe}\nname: {name}\n---\n\n{content}"
    )
    dest.write_text(body, encoding="utf-8")
    return {"ok": True, "path": str(dest), **list_skills()}


def import_skill_file(source: str) -> dict:
    src = Path(source).expanduser().resolve()
    if not src.is_file():
        return {"ok": False, "message": f"Not a file: {src}"}
    dest = _user_skills_dir() / src.name
    shutil.copy2(src, dest)
    return {"ok": True, "path": str(dest), **list_skills()}


def remove_skill(skill_id: str) -> dict:
    info = get_skill(skill_id)
    if not info.get("ok"):
        return info
    path = Path(str(info["path"]))
    try:
        path.relative_to(_user_skills_dir())
    except ValueError:
        return {"ok": False, "message": "Only user-installed skills under ~/.config/dana/skills can be removed."}
    path.unlink(missing_ok=True)
    return {"ok": True, "removed": str(path), **list_skills()}


def import_skill_pack(pack: str) -> dict:
    """Shallow-clone a known upstream skill repo and copy markdown into user skills."""
    key = (pack or "").strip().lower()
    if key not in KNOWN_PACKS:
        return {
            "ok": False,
            "message": f"Unknown pack: {pack}. Known: {', '.join(KNOWN_PACKS)}",
            "known_packs": list(KNOWN_PACKS.keys()),
        }
    meta = KNOWN_PACKS[key]
    if not shutil.which("git"):
        return {"ok": False, "message": "git is required to import skill packs."}

    dest_root = _user_skills_dir() / f"pack-{key}"
    dest_root.mkdir(parents=True, exist_ok=True)
    imported: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dana-skill-pack-") as tmp:
        tmp_path = Path(tmp) / key
        cmd = [
            "git", "clone", "--depth", "1", "--single-branch",
            str(meta["url"]), str(tmp_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=clean_subprocess_env())
        except Exception as exc:
            return {"ok": False, "message": f"git clone failed: {exc}"}
        if result.returncode != 0:
            return {
                "ok": False,
                "message": (result.stderr or result.stdout or "git clone failed")[:500],
            }

        candidates: list[Path] = []
        for pattern in meta.get("globs", ["**/*.md"]):
            candidates.extend(tmp_path.glob(pattern))
        # Prefer shorter skill-like files
        uniq: list[Path] = []
        seen: set[str] = set()
        for path in sorted(candidates, key=lambda p: (len(p.parts), p.stat().st_size if p.is_file() else 10**9)):
            if not path.is_file():
                continue
            name = path.name.lower()
            if name in {"license.md", "changelog.md", "readme.md", "contributing.md"}:
                # still allow readme if tiny skill repos
                if path.stat().st_size > 12_000:
                    continue
            key_path = str(path.relative_to(tmp_path))
            if key_path in seen:
                continue
            seen.add(key_path)
            candidates_ok = path
            uniq.append(candidates_ok)
            if len(uniq) >= int(meta.get("max_files", 30)):
                break

        for path in uniq:
            rel = path.relative_to(tmp_path)
            safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", "-".join(rel.with_suffix("").parts))
            if not safe_name.endswith(".md"):
                out = dest_root / f"{safe_name}.md"
            else:
                out = dest_root / safe_name
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(text) > 80_000:
                text = text[:80_000] + "\n\n…\n"
            if not text.lstrip().startswith("---"):
                text = (
                    f"---\nid: {safe_name}\nname: {safe_name.replace('-', ' ')}\n"
                    f"description: Imported from {key}\ntags: pack,{key}\n---\n\n{text}"
                )
            out.write_text(text, encoding="utf-8")
            imported.append(str(out))

    with _LOCK:
        reg = _load_registry()
        paths = [str(p) for p in reg.get("extra_paths", [])]
        root = str(dest_root.resolve())
        if root not in paths:
            paths.append(root)
        reg["extra_paths"] = paths
        _save_registry(reg)

    listing = list_skills()
    return {
        "ok": True,
        "pack": key,
        "imported": len(imported),
        "files": imported[:20],
        "message": f"Imported {len(imported)} skill file(s) from {key}.",
        **listing,
    }


def active_skill_context(max_chars: int = 12000) -> str:
    listed = list_skills()
    chunks: list[str] = []
    total = 0
    for item in listed.get("skills", []):
        if not item.get("enabled"):
            continue
        full = get_skill(str(item["id"]))
        if not full.get("ok"):
            continue
        body = str(full.get("content") or "").strip()
        if not body:
            continue
        header = f"## Skill: {full.get('name') or item['id']}"
        piece = header + "\n" + body
        if total + len(piece) > max_chars:
            remain = max_chars - total
            if remain > 200:
                chunks.append(piece[:remain] + "\n…")
            break
        chunks.append(piece)
        total += len(piece)
    return "\n\n".join(chunks)

def pack_status() -> dict:
    """Report which known packs are present under user skills."""
    reg = _load_registry()
    packs = []
    for key in KNOWN_PACKS:
        dest = _user_skills_dir() / f"pack-{key}"
        count = 0
        if dest.is_dir():
            count = sum(1 for _ in dest.rglob("*.md"))
        packs.append({
            "id": key,
            "installed": dest.is_dir() and count > 0,
            "path": str(dest),
            "files": count,
            "url": KNOWN_PACKS[key]["url"],
        })
    return {
        "ok": True,
        "packs": packs,
        "last_sync": reg.get("last_pack_sync"),
    }


def sync_skill_pack(pack: str = "") -> dict:
    """Re-import one pack or all installed known packs (fresh shallow clone)."""
    key = (pack or "").strip().lower()
    targets = [key] if key else [p["id"] for p in pack_status().get("packs", []) if p.get("installed")]
    if key and key not in KNOWN_PACKS:
        return {"ok": False, "message": f"Unknown pack: {pack}", "known_packs": list(KNOWN_PACKS.keys())}
    if not targets:
        targets = list(KNOWN_PACKS.keys())  # first-time: offer nothing special — sync all keys means install missing
        targets = [k for k in KNOWN_PACKS]  # explicit all

    results = []
    ok_all = True
    for name in targets:
        dest = _user_skills_dir() / f"pack-{name}"
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        result = import_skill_pack(name)
        results.append({"pack": name, "ok": bool(result.get("ok")), "message": result.get("message"), "imported": result.get("imported", 0)})
        if not result.get("ok"):
            ok_all = False

    with _LOCK:
        reg = _load_registry()
        import time as _time
        reg["last_pack_sync"] = _time.time()
        _save_registry(reg)

    listing = list_skills()
    return {
        "ok": ok_all,
        "results": results,
        "message": f"Synced {sum(1 for r in results if r['ok'])}/{len(results)} pack(s).",
        **listing,
    }
