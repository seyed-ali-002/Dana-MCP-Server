"""Dana Computer Use — observe → plan → act → verify loop for GUI agents.

Philosophy (aligned with Claude Computer Use, adapted for Linux/Wayland):
- Prefer browser automation (Playwright) for web tasks
- Prefer accessibility when available
- Fall back to screenshot + coordinates via desktop backends
- Always observe after mutating actions when verify is requested
- Safety tiers + emergency stop
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from dana.subprocess_env import clean_subprocess_env

_log = logging.getLogger("dana.computer_use")
_STOP = threading.Event()
_HISTORY: list[dict[str, Any]] = []
_HISTORY_LOCK = threading.Lock()
_HISTORY_MAX = 80
_LAST_SHOT_HASH: str | None = None

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

SAFE_ACTIONS = {
    "observe", "screenshot", "screenshot_region", "windows", "cursor", "active_window",
    "accessibility", "diagnostics", "status", "wait", "wait_for_window", "wait_for_text",
    "screen_changed", "verify", "locate_text", "inspect_region", "move", "scroll",
    "position", "list_history", "clear_history",
}
MODERATE_ACTIONS = {
    "click", "double_click", "right_click", "drag", "type", "key", "hotkey",
    "open_app", "focus", "activate", "close", "minimize", "maximize",
    "press_shortcut", "type_into",
}
DANGEROUS_ACTIONS = {
    "delete", "sudo", "shutdown", "reboot", "format", "rm", "kill_all",
}


def _classify(action: str) -> str:
    a = (action or "").strip().lower()
    if a in DANGEROUS_ACTIONS or a.startswith("danger_"):
        return "dangerous"
    if a in SAFE_ACTIONS:
        return "safe"
    if a in MODERATE_ACTIONS:
        return "moderate"
    return "moderate"


def emergency_stop(enabled: bool = True) -> dict[str, Any]:
    if enabled:
        _STOP.set()
    else:
        _STOP.clear()
    return {"ok": True, "stopped": _STOP.is_set(), "message": "Computer Use STOP engaged" if enabled else "Computer Use resumed"}


def _check_stop() -> None:
    if _STOP.is_set():
        raise RuntimeError(
            "Computer Use emergency stop is active. Call computer_use_stop(enabled=false) to resume."
        )


def _store(*parts: str) -> Path:
    root = Path.home() / ".config" / "dana" / "computer_use"
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _record(entry: dict[str, Any]) -> None:
    with _HISTORY_LOCK:
        _HISTORY.append({**entry, "ts": time.time()})
        del _HISTORY[:-_HISTORY_MAX]


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------

def _screenshot(path: str = "", region: tuple[int, int, int, int] | None = None) -> dict[str, Any]:
    from dana.tools import desktop_agent as da

    if region is None:
        return da.take_screenshot(path)
    x, y, w, h = region
    full = da.take_screenshot("")
    if not full.get("ok"):
        return full
    src = Path(str(full.get("path") or ""))
    if not src.is_file():
        return {"ok": False, "error": "Screenshot file missing after capture"}
    out = Path(path).expanduser() if path else _store("regions", f"region-{int(time.time()*1000)}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        img = Image.open(src)
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(img.width, x0 + max(1, int(w))), min(img.height, y0 + max(1, int(h)))
        crop = img.crop((x0, y0, x1, y1))
        crop.save(out)
        return {"ok": True, "path": str(out), "region": [x0, y0, x1 - x0, y1 - y0], "backend": "pil-crop", "full": str(src)}
    except Exception as exc:
        # Fallback: return full shot with region metadata
        return {"ok": True, "path": str(src), "region": [x, y, w, h], "crop_error": str(exc), "backend": full.get("backend")}


def _file_hash(path: str | Path) -> str | None:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return hashlib.sha256(data).hexdigest()[:16]


def _screen_size() -> dict[str, int]:
    try:
        import pyautogui

        w, h = pyautogui.size()
        return {"width": int(w), "height": int(h)}
    except Exception:
        return {"width": 0, "height": 0}


def observe(
    *,
    include_screenshot: bool = True,
    include_accessibility: bool = False,
    region: list[int] | None = None,
    max_a11y_nodes: int = 60,
) -> dict[str, Any]:
    """Single composite observation for the agent loop."""
    from dana.tools import desktop_agent as da

    _check_stop()
    result: dict[str, Any] = {
        "ok": True,
        "os": platform.system(),
        "session": os.getenv("XDG_SESSION_TYPE", ""),
        "screen": _screen_size(),
        "stopped": _STOP.is_set(),
    }
    wins = da.list_windows()
    result["windows"] = wins.get("windows", [])
    result["window_count"] = wins.get("count", 0)
    active = None
    if result["windows"]:
        # Prefer first match with desktop >=0 or just first
        active = result["windows"][0]
    result["active_window"] = active

    shot = None
    if include_screenshot:
        if region and len(region) == 4:
            shot = _screenshot("", (int(region[0]), int(region[1]), int(region[2]), int(region[3])))
        else:
            shot = da.take_screenshot("")
        result["screenshot"] = shot
        if shot and shot.get("path"):
            global _LAST_SHOT_HASH
            _LAST_SHOT_HASH = _file_hash(shot["path"])
            result["screenshot_hash"] = _LAST_SHOT_HASH

    if include_accessibility:
        result["accessibility"] = da.accessibility_tree(max_nodes=max_a11y_nodes)

    try:
        from dana.tools.desktop_agent import desktop_input_status

        result["input_ready"] = desktop_input_status()
    except Exception as exc:
        result["input_ready"] = {"ok": False, "error": str(exc)}

    result["guidance"] = (
        "Prefer browser tools for web. Prefer accessibility names when available. "
        "Use coordinates only as fallback. After each mutating action, call computer_observe or set verify=true."
    )
    _record({"kind": "observe", "window_count": result["window_count"], "hash": result.get("screenshot_hash")})
    return result


def locate_text(query: str, path: str = "", lang: str = "eng") -> dict[str, Any]:
    """OCR locate text on a screenshot (tesseract if installed)."""
    _check_stop()
    q = (query or "").strip()
    if not q:
        raise ValueError("query is required")
    shot = _screenshot(path) if not path else {"ok": True, "path": path}
    if not shot.get("ok"):
        return shot
    img_path = str(shot.get("path") or "")
    if not shutil.which("tesseract"):
        return {
            "ok": False,
            "path": img_path,
            "error": "tesseract not installed. Install tesseract-ocr for locate_text, or use vision model on the screenshot path.",
            "screenshot": img_path,
        }
    # tesseract TSV for bounding boxes
    import subprocess

    try:
        p = subprocess.run(
            ["tesseract", img_path, "stdout", "--psm", "11", "-l", lang, "tsv"],
            capture_output=True,
            text=True,
            timeout=60,
            env=clean_subprocess_env(),
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": img_path}
    matches = []
    lines = (p.stdout or "").splitlines()
    if len(lines) > 1:
        for line in lines[1:]:
            cols = line.split("\t")
            if len(cols) < 12:
                continue
            text = cols[11].strip()
            if not text:
                continue
            if q.lower() in text.lower():
                try:
                    left, top, width, height = int(cols[6]), int(cols[7]), int(cols[8]), int(cols[9])
                except ValueError:
                    continue
                matches.append({
                    "text": text,
                    "x": left,
                    "y": top,
                    "w": width,
                    "h": height,
                    "cx": left + width // 2,
                    "cy": top + height // 2,
                    "conf": cols[10],
                })
    return {
        "ok": bool(matches),
        "query": q,
        "path": img_path,
        "matches": matches[:30],
        "count": len(matches),
        "tesseract_rc": p.returncode,
    }


def screen_changed(previous_hash: str = "", path: str = "", timeout_s: float = 0) -> dict[str, Any]:
    """Compare current screenshot hash to previous (or last observe)."""
    global _LAST_SHOT_HASH
    prev = previous_hash or _LAST_SHOT_HASH or ""
    deadline = time.time() + max(0.0, float(timeout_s))
    last = {}
    while True:
        shot = _screenshot(path)
        h = _file_hash(shot.get("path") or "") if shot.get("ok") else None
        last = {"ok": True, "changed": bool(prev and h and h != prev), "previous": prev, "current": h, "screenshot": shot}
        if last["changed"] or timeout_s <= 0 or time.time() >= deadline:
            if h:
                _LAST_SHOT_HASH = h
            return last
        time.sleep(0.35)


def wait_until(
    condition: str,
    timeout_s: float = 15.0,
    poll_s: float = 0.5,
    query: str = "",
) -> dict[str, Any]:
    """Wait for window:TITLE, text:OCR, screen_changed, or input_ready."""
    from dana.tools import desktop_agent as da

    _check_stop()
    cond = (condition or "").strip().lower()
    deadline = time.time() + max(0.5, float(timeout_s))
    last: dict[str, Any] = {}
    while time.time() < deadline:
        _check_stop()
        if cond.startswith("window:") or cond == "window":
            title = query or condition.split(":", 1)[-1]
            last = da.wait_for(title, timeout_s=min(1.0, poll_s * 2), poll_s=poll_s)
            if last.get("ok"):
                return {"ok": True, "condition": condition, **last}
        elif cond.startswith("text:") or cond == "text":
            q = query or condition.split(":", 1)[-1]
            last = locate_text(q)
            if last.get("matches"):
                return {"ok": True, "condition": condition, **last}
        elif cond in {"screen_changed", "changed"}:
            last = screen_changed(timeout_s=0)
            if last.get("changed"):
                return {"ok": True, "condition": condition, **last}
        elif cond in {"input_ready", "ready"}:
            from dana.tools.desktop_agent import desktop_input_status

            last = desktop_input_status()
            if last.get("ready"):
                return {"ok": True, "condition": condition, **last}
        else:
            raise ValueError("condition must be window:Title, text:Label, screen_changed, or input_ready")
        time.sleep(max(0.1, float(poll_s)))
    return {"ok": False, "condition": condition, "error": f"Timed out after {timeout_s}s", "last": last}


# ---------------------------------------------------------------------------
# Action execution with safety + optional verify
# ---------------------------------------------------------------------------

def _run_input(action: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch to ydotool/xdotool/pyautogui via desktop_agent helpers / local_agent."""
    from dana.tools import local_agent as la
    import platform as _pf

    system = _pf.system()
    action = action.lower()
    if system == "Linux":
        try:
            backend = la._desktop_backend()
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        if backend == "ydotool":
            if action == "double_click":
                return la._desktop_ydo("click", int(kwargs.get("x", 0)), int(kwargs.get("y", 0)), "left", 2, 0, "", "")
            if action == "right_click":
                return la._desktop_ydo("click", int(kwargs.get("x", 0)), int(kwargs.get("y", 0)), "right", 1, 0, "", "")
            if action in {"move", "move_relative", "click", "scroll", "type", "key", "hotkey"}:
                return la._desktop_ydo(
                    action,
                    int(kwargs.get("x", 0)),
                    int(kwargs.get("y", 0)),
                    str(kwargs.get("button", "left")),
                    int(kwargs.get("clicks", 1)),
                    int(kwargs.get("scroll", 0)),
                    str(kwargs.get("text", "")),
                    str(kwargs.get("key", "")),
                )
        if backend == "xdotool":
            # thin wrappers
            x, y = int(kwargs.get("x", 0)), int(kwargs.get("y", 0))
            if action == "move":
                return la._run(["xdotool", "mousemove", str(max(0, x)), str(max(0, y))], 5)
            if action == "click":
                return la._run(["xdotool", "mousemove", str(max(0, x)), str(max(0, y)), "click", "1"], 5)
            if action == "type":
                return la._run(["xdotool", "type", "--clearmodifiers", "--delay", "1", str(kwargs.get("text", ""))])
            if action == "key":
                return la._run(["xdotool", "key", "--clearmodifiers", str(kwargs.get("key", ""))])
            if action == "hotkey":
                parts = [p.strip() for p in str(kwargs.get("key", "")).replace("+", " ").split() if p.strip()]
                return la._run(["xdotool", "key", "--clearmodifiers", "+".join(parts)])
    try:
        import pyautogui

        pyautogui.FAILSAFE = True
        x, y = int(kwargs.get("x", 0)), int(kwargs.get("y", 0))
        if action == "move":
            pyautogui.moveTo(max(0, x), max(0, y)); return {"ok": True, "backend": "pyautogui"}
        if action == "click":
            pyautogui.click(x=max(0, x), y=max(0, y), clicks=int(kwargs.get("clicks", 1)), button=kwargs.get("button", "left")); return {"ok": True, "backend": "pyautogui"}
        if action == "double_click":
            pyautogui.doubleClick(x=max(0, x), y=max(0, y)); return {"ok": True, "backend": "pyautogui"}
        if action == "right_click":
            pyautogui.click(x=max(0, x), y=max(0, y), button="right"); return {"ok": True, "backend": "pyautogui"}
        if action == "type":
            pyautogui.write(str(kwargs.get("text", "")), interval=0.001); return {"ok": True, "backend": "pyautogui"}
        if action == "key":
            pyautogui.press(str(kwargs.get("key", ""))); return {"ok": True, "backend": "pyautogui"}
        if action == "hotkey":
            parts = [p.strip().lower() for p in str(kwargs.get("key", "")).replace("+", " ").split() if p.strip()]
            pyautogui.hotkey(*parts); return {"ok": True, "backend": "pyautogui"}
        if action == "scroll":
            pyautogui.scroll(int(kwargs.get("scroll", 0))); return {"ok": True, "backend": "pyautogui"}
        if action == "drag":
            pyautogui.moveTo(max(0, x), max(0, y))
            pyautogui.dragTo(int(kwargs.get("x2", 0)), int(kwargs.get("y2", 0)), duration=0.2)
            return {"ok": True, "backend": "pyautogui"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": f"Unsupported action for available backends: {action}"}


def act(
    action: str,
    *,
    x: int = 0,
    y: int = 0,
    x2: int = 0,
    y2: int = 0,
    text: str = "",
    key: str = "",
    query: str = "",
    button: str = "left",
    clicks: int = 1,
    scroll: int = 0,
    confirm_dangerous: bool = False,
    verify: bool = False,
    verify_query: str = "",
    observe_after: bool = False,
    prefer: str = "auto",
) -> dict[str, Any]:
    """Execute one computer-use action with safety + optional verification."""
    from dana.tools import desktop_agent as da

    _check_stop()
    action_l = (action or "").strip().lower()
    tier = _classify(action_l)
    if tier == "dangerous" and not confirm_dangerous:
        return {
            "ok": False,
            "safety": tier,
            "needs_confirmation": True,
            "message": f"Action {action_l!r} is classified dangerous. Re-call with confirm_dangerous=true after user approval.",
        }

    result: dict[str, Any] = {"action": action_l, "safety": tier}
    prefer_l = (prefer or "auto").lower()

    # High-level routing
    if action_l in {"observe", "screenshot"}:
        result["result"] = observe(include_screenshot=True)
    elif action_l == "open_app":
        result["result"] = da.open_application(query or text)
        if result["result"].get("ok"):
            result["wait"] = da.wait_for(query or text, timeout_s=10)
    elif action_l in {"focus", "activate"}:
        result["result"] = da.focus_window(query or text)
    elif action_l == "close":
        from dana.tools.desktop_agent import _run as _dr
        target = (query or text).strip()
        if not target:
            result["result"] = {"ok": False, "error": "query/text window title or id required for close"}
        elif not shutil.which("wmctrl"):
            result["result"] = {"ok": False, "error": "wmctrl required for close"}
        elif target.startswith("0x"):
            result["result"] = _dr(["wmctrl", "-ic", target])
        else:
            result["result"] = _dr(["wmctrl", "-c", target])
    elif action_l in {"click", "double_click", "right_click", "move", "drag", "scroll", "type", "key", "hotkey", "type_into", "press_shortcut"}:
        # Element-by-name path
        if query and action_l in {"click", "double_click", "right_click"} and prefer_l in {"auto", "a11y", "accessibility"}:
            acc = da.find_accessible(query)
            focused = da.focus_window(query)
            result["resolve"] = {"accessibility": acc, "focus": focused}
            # OCR fallback for coordinates
            if prefer_l in {"auto", "vision", "ocr"} or not (focused.get("ok") and isinstance(focused.get("window") or (focused.get("matches") or [None])[0], dict) and (focused.get("window") or {}).get("w")):
                ocr = locate_text(query)
                result["resolve"]["ocr"] = {"count": ocr.get("count"), "matches": (ocr.get("matches") or [])[:5]}
                if ocr.get("matches"):
                    m = ocr["matches"][0]
                    x, y = int(m["cx"]), int(m["cy"])
            else:
                winfo = focused.get("window") or (focused.get("matches") or [{}])[0]
                if isinstance(winfo, dict) and winfo.get("w"):
                    x = int(winfo["x"]) + int(winfo["w"]) // 2
                    y = int(winfo["y"]) + int(winfo["h"]) // 2
        act_map = action_l
        if action_l == "type_into":
            act_map = "type"
        if action_l == "press_shortcut":
            act_map = "hotkey"
            key = key or text or query
        result["result"] = _run_input(
            act_map, x=x, y=y, x2=x2, y2=y2, text=text, key=key or text,
            button=button, clicks=clicks, scroll=scroll,
        )
    elif action_l == "wait":
        result["result"] = wait_until(query or text or "screen_changed", timeout_s=float(x or 15))
    elif action_l == "locate_text":
        result["result"] = locate_text(query or text)
    else:
        raise ValueError(
            f"Unknown action {action!r}. Use observe, open_app, focus, click, type, key, hotkey, wait, locate_text, …"
        )

    ok = True
    inner = result.get("result")
    if isinstance(inner, dict) and "ok" in inner:
        ok = bool(inner["ok"])

    if verify or verify_query:
        vq = verify_query or query
        if vq:
            result["verify"] = da.verify_window(vq)
            ok = ok and bool(result["verify"].get("ok"))
        else:
            result["verify"] = screen_changed(timeout_s=0)

    if observe_after:
        result["observation"] = observe(include_screenshot=True)

    result["ok"] = ok
    _record({"kind": "act", "action": action_l, "ok": ok, "safety": tier})
    return result


def agent_step(
    goal: str,
    note: str = "",
    include_accessibility: bool = False,
) -> dict[str, Any]:
    """One loop iteration support: full observe + history hint for the LLM planner.

    The LLM remains the planner; this tool packages state so the model can decide
    the next computer_act without juggling many low-level tools.
    """
    _check_stop()
    obs = observe(include_screenshot=True, include_accessibility=include_accessibility)
    with _HISTORY_LOCK:
        recent = list(_HISTORY[-8:])
    return {
        "ok": True,
        "goal": goal,
        "note": note,
        "observation": obs,
        "recent_actions": recent,
        "stop": _STOP.is_set(),
        "planner_hint": (
            "1) Read observation.screenshot path (vision). "
            "2) Prefer open_app/focus/wait_until before coordinates. "
            "3) computer_act(..., verify=true) after mutations. "
            "4) On failure: locate_text → retry → alternative hotkey. "
            "5) For web: use Dana browser tool instead of screen control. "
            "6) Emergency: computer_use_stop(true)."
        ),
    }


def history(limit: int = 20) -> dict[str, Any]:
    with _HISTORY_LOCK:
        items = list(_HISTORY[-max(1, min(int(limit), _HISTORY_MAX)):])
    return {"ok": True, "count": len(items), "items": items}


def clear_history() -> dict[str, Any]:
    with _HISTORY_LOCK:
        _HISTORY.clear()
    return {"ok": True, "cleared": True}


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

def register_computer_use_tools(mcp) -> None:
    try:
        from dana.tools.mcp_quality import MUTATING, READ_ONLY
    except Exception:
        def READ_ONLY(x):  # type: ignore
            return None
        def MUTATING(x):  # type: ignore
            return None

    @mcp.tool()
    def computer_observe(
        include_screenshot: bool = True,
        include_accessibility: bool = False,
        region: str = "",
    ) -> dict[str, Any]:
        """Composite desktop observation: screen size, windows, screenshot, optional a11y.

        region: optional \"x,y,w,h\" crop for zoomed inspection.
        """
        reg = None
        if region.strip():
            parts = [int(p.strip()) for p in region.split(",")]
            if len(parts) == 4:
                reg = parts
        return observe(
            include_screenshot=include_screenshot,
            include_accessibility=include_accessibility,
            region=reg,
        )

    @mcp.tool()
    def computer_act(
        action: str,
        x: int = 0,
        y: int = 0,
        x2: int = 0,
        y2: int = 0,
        text: str = "",
        key: str = "",
        query: str = "",
        button: str = "left",
        clicks: int = 1,
        scroll: int = 0,
        confirm_dangerous: bool = False,
        verify: bool = False,
        verify_query: str = "",
        observe_after: bool = False,
        prefer: str = "auto",
    ) -> dict[str, Any]:
        """Execute a Computer Use action (open_app, focus, click, type, key, hotkey, wait, locate_text, …).

        Set verify=true to check window/state after action. prefer=auto|a11y|ocr|coords.
        """
        return act(
            action,
            x=x, y=y, x2=x2, y2=y2, text=text, key=key, query=query,
            button=button, clicks=clicks, scroll=scroll,
            confirm_dangerous=confirm_dangerous, verify=verify,
            verify_query=verify_query, observe_after=observe_after, prefer=prefer,
        )

    @mcp.tool()
    def computer_wait(condition: str, timeout_s: float = 15.0, query: str = "", poll_s: float = 0.5) -> dict[str, Any]:
        """Wait until window:Title, text:Label (OCR), screen_changed, or input_ready."""
        return wait_until(condition, timeout_s=timeout_s, poll_s=poll_s, query=query)

    @mcp.tool()
    def computer_locate_text(query: str, path: str = "", lang: str = "eng") -> dict[str, Any]:
        """OCR-locate text on screen (needs tesseract-ocr). Returns bounding boxes + centers."""
        return locate_text(query, path=path, lang=lang)

    @mcp.tool()
    def computer_agent_step(goal: str, note: str = "", include_accessibility: bool = False) -> dict[str, Any]:
        """One Computer Use loop package: observation + recent history + planner hints for the model."""
        return agent_step(goal, note=note, include_accessibility=include_accessibility)

    @mcp.tool()
    def computer_use_stop(enabled: bool = True) -> dict[str, Any]:
        """Emergency stop (true) or resume (false) for all computer_act / observe mutations."""
        return emergency_stop(enabled)

    @mcp.tool()
    def computer_history(limit: int = 20) -> dict[str, Any]:
        """Recent Computer Use actions for recovery/planning."""
        return history(limit)

    @mcp.tool()
    def computer_status() -> dict[str, Any]:
        """Computer Use subsystem status: stop flag, input readiness, backends."""
        from dana.tools.desktop_agent import desktop_input_status
        from dana.tools.zero_computer import desktop_control_bridge_status

        return {
            "ok": True,
            "stopped": _STOP.is_set(),
            "input": desktop_input_status(),
            "bridge": desktop_control_bridge_status(),
            "tesseract": bool(shutil.which("tesseract")),
            "pil": _pil_available(),
            "history_len": len(_HISTORY),
        }


def _pil_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False
