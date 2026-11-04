"""Dana skills registry — load, list, and apply markdown skill packs.

Skills are plain Markdown (or text) files that instruct the agent how to work.
Sources:
  - ~/.config/dana/skills/
  - <project>/skills/
  - bundled dana/skill_packs/
  - user-uploaded paths registered via the Skills UI / tools
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from threading import RLock

_LOCK = RLock()


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
        return {"extra_paths": [], "enabled": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"extra_paths": [], "enabled": []}


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
        for pattern in ("*.md", "*.txt", "*.skill.md"):
            for path in sorted(root.rglob(pattern)):
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


def list_skills() -> dict:
    items = []
    reg = _load_registry()
    enabled = set(reg.get("enabled") or [])
    for path in _iter_skill_files():
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            items.append({"id": path.stem, "path": str(path), "error": str(exc)})
            continue
        meta, body = _parse_frontmatter(raw)
        skill_id = meta.get("id") or path.stem
        items.append({
            "id": skill_id,
            "name": meta.get("name") or skill_id.replace("-", " ").title(),
            "description": meta.get("description") or body.strip().splitlines()[0][:160] if body.strip() else "",
            "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
            "path": str(path),
            "enabled": (not enabled) or skill_id in enabled or path.stem in enabled,
            "chars": len(body),
        })
    return {"ok": True, "count": len(items), "skills": items, "extra_paths": reg.get("extra_paths", [])}


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
    dest.write_text(content if content.lstrip().startswith("---") else f"---\nid: {safe}\nname: {name}\n---\n\n{content}", encoding="utf-8")
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
    # Only allow deleting from user skills dir
    try:
        path.relative_to(_user_skills_dir())
    except ValueError:
        return {"ok": False, "message": "Only user-installed skills under ~/.config/dana/skills can be removed."}
    path.unlink(missing_ok=True)
    return {"ok": True, "removed": str(path), **list_skills()}


def active_skill_context(max_chars: int = 12000) -> str:
    """Concatenate enabled skill bodies for agent context (token-aware trim)."""
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
