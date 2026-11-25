"""High-level desktop agent layer for Dana.

Builds on desktop_control backends (ydotool / xdotool / pyautogui):
- Wayland input setup helpers (uinput rule text + ydotoold socket)
- Observation (screenshot / windows) separate from input
- Verification after actions
- High-level open / focus / wait / click_element / type_into
- Optional AT-SPI accessibility probe when pyatspi is available
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from dana.subprocess_env import clean_subprocess_env

_log = logging.getLogger("dana.desktop_agent")


def _run(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=max(1, min(timeout, 120)),
            check=False,
            env=clean_subprocess_env(),
        )
    except FileNotFoundError as exc:
        return {"ok": False, "command": cmd, "error": f"Command not found: {cmd[0]}", "exception": str(exc)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "command": cmd, "error": f"Timed out after {timeout}s"}
    return {
        "ok": p.returncode == 0,
        "command": cmd,
        "returncode": p.returncode,
        "stdout": (p.stdout or "")[-20000:],
        "stderr": (p.stderr or "")[-8000:],
    }


def _store(*parts: str) -> Path:
    root = Path.home() / ".config" / "dana"
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def setup_wayland_input(*, start_daemon: bool = True) -> dict[str, Any]:
    """Prepare / document uinput + ydotoold so desktop_control can inject input on Wayland."""
    if platform.system() != "Linux":
        return {"ok": True, "skipped": True, "message": "Not Linux; pyautogui backend is used."}

    steps: list[dict[str, Any]] = []
    uid = os.getuid() if hasattr(os, "getuid") else 0
    gid = os.getgid() if hasattr(os, "getgid") else 0

    # 1) uinput module hint
    uinput = Path("/dev/uinput")
    steps.append({"step": "uinput_device", "exists": uinput.exists(), "writable": os.access(uinput, os.W_OK) if uinput.exists() else False})

    # 2) Write udev rule + modules-load snippets under ~/.config/dana for the user to install with sudo
    udev_body = (
        "# Dana: allow users in group input to write uinput\n"
        'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"\n'
    )
    udev_path = _store("desktop", "99-dana-uinput.rules")
    udev_path.write_text(udev_body, encoding="utf-8")
    modules_path = _store("desktop", "dana-uinput.conf")
    modules_path.write_text("uinput\n", encoding="utf-8")
    install_script = _store("desktop", "install-wayland-input.sh")
    install_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"install -m 0644 {udev_path} /etc/udev/rules.d/99-dana-uinput.rules\n"
        f"install -m 0644 {modules_path} /etc/modules-load.d/dana-uinput.conf\n"
        "modprobe uinput || true\n"
        "udevadm control --reload-rules\n"
        "udevadm trigger\n"
        "# ensure user is in input group\n"
        f"usermod -aG input \"$(id -un)\" || true\n"
        "echo 'Re-login may be required for group input to apply.'\n",
        encoding="utf-8",
    )
    try:
        install_script.chmod(install_script.stat().st_mode | 0o111)
    except OSError:
        pass
    steps.append({
        "step": "wrote_helpers",
        "udev_rule": str(udev_path),
        "modules_load": str(modules_path),
        "install_script": str(install_script),
        "sudo_hint": f"sudo bash {install_script}",
    })

    # 3) Socket paths
    runtime = os.getenv("XDG_RUNTIME_DIR", "").strip()
    socket_candidates = []
    if runtime:
        socket_candidates.append(Path(runtime) / ".ydotool_socket")
    socket_candidates.append(Path(f"/run/dana-ydotool-{uid}/.ydotool_socket"))
    socket_candidates.append(Path("/tmp/.ydotool_socket"))

    existing = next((p for p in socket_candidates if p.exists()), None)
    steps.append({"step": "existing_socket", "path": str(existing) if existing else None})

    # 4) Start ydotoold as current user if possible (works when uinput is writable or daemon already root)
    daemon_started = False
    socket_path = existing
    if start_daemon and shutil.which("ydotoold") and not existing:
        preferred = Path(runtime) / ".ydotool_socket" if runtime else Path("/tmp/.ydotool_socket")
        try:
            # Prefer user-owned socket in XDG_RUNTIME_DIR
            env = clean_subprocess_env()
            env["YDOTOOL_SOCKET"] = str(preferred)
            # modern ydotoold may accept --socket-path
            cmd = ["ydotoold"]
            # Some builds support flags; try plain first then with socket path via env only
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
            time.sleep(0.4)
            if preferred.exists() or Path("/tmp/.ydotool_socket").exists():
                socket_path = preferred if preferred.exists() else Path("/tmp/.ydotool_socket")
                os.environ["YDOTOOL_SOCKET"] = str(socket_path)
                daemon_started = True
            else:
                # leave process; may still create socket shortly
                daemon_started = proc.poll() is None
            steps.append({"step": "start_ydotoold", "ok": daemon_started, "pid": proc.pid if daemon_started else None})
        except OSError as exc:
            steps.append({"step": "start_ydotoold", "ok": False, "error": str(exc)})

    if socket_path and socket_path.exists():
        os.environ["YDOTOOL_SOCKET"] = str(socket_path)

    ready = bool(
        shutil.which("ydotool")
        and (
            (uinput.exists() and os.access(uinput, os.W_OK))
            or (socket_path and socket_path.exists())
        )
    )

    message = (
        "Wayland input ready."
        if ready
        else (
            "Wayland input not fully ready. Run the install script with sudo, re-login (group input), "
            "then call desktop_agent(action='setup_input') again. "
            f"Script: {install_script}"
        )
    )
    return {
        "ok": ready,
        "ready": ready,
        "message": message,
        "steps": steps,
        "YDOTOOL_SOCKET": os.getenv("YDOTOOL_SOCKET", ""),
        "install_script": str(install_script),
    }


def list_windows() -> dict[str, Any]:
    if shutil.which("wmctrl"):
        r = _run(["wmctrl", "-lG"])
        windows = []
        for line in (r.get("stdout") or "").splitlines():
            parts = line.split(None, 7)
            if len(parts) >= 8:
                windows.append({
                    "id": parts[0],
                    "desktop": parts[1],
                    "x": int(parts[2]) if parts[2].lstrip("-").isdigit() else 0,
                    "y": int(parts[3]) if parts[3].lstrip("-").isdigit() else 0,
                    "w": int(parts[4]) if parts[4].isdigit() else 0,
                    "h": int(parts[5]) if parts[5].isdigit() else 0,
                    "host": parts[6],
                    "title": parts[7],
                })
            elif len(parts) >= 4:
                windows.append({"id": parts[0], "title": parts[-1], "raw": line})
        return {"ok": r.get("ok", False), "backend": "wmctrl", "windows": windows, "count": len(windows)}
    if shutil.which("xdotool") and os.getenv("XDG_SESSION_TYPE", "").lower() != "wayland":
        r = _run(["xdotool", "search", "--name", ".*"])
        ids = [x for x in (r.get("stdout") or "").split() if x]
        windows = []
        for wid in ids[:40]:
            t = _run(["xdotool", "getwindowname", wid], timeout=5)
            windows.append({"id": wid, "title": (t.get("stdout") or "").strip()})
        return {"ok": True, "backend": "xdotool", "windows": windows, "count": len(windows)}
    return {"ok": False, "error": "Install wmctrl (recommended) or xdotool for window listing.", "windows": []}


def find_window(query: str) -> dict[str, Any]:
    q = (query or "").strip().lower()
    if not q:
        raise ValueError("query is required")
    listed = list_windows()
    matches = [w for w in listed.get("windows", []) if q in str(w.get("title", "")).lower() or q == str(w.get("id", "")).lower()]
    return {"ok": bool(matches), "query": query, "matches": matches, "count": len(matches), "backend": listed.get("backend")}


def focus_window(query: str) -> dict[str, Any]:
    found = find_window(query)
    if not found.get("matches"):
        return {"ok": False, "error": f"No window matching {query!r}", **found}
    target = found["matches"][0]
    wid = str(target.get("id") or "")
    title = str(target.get("title") or query)
    if shutil.which("wmctrl"):
        if wid.startswith("0x"):
            r = _run(["wmctrl", "-ia", wid])
        else:
            r = _run(["wmctrl", "-a", title])
        return {"ok": r.get("ok", False), "action": "focus", "window": target, **r}
    if shutil.which("xdotool") and wid:
        r = _run(["xdotool", "windowactivate", wid])
        return {"ok": r.get("ok", False), "action": "focus", "window": target, **r}
    return {"ok": False, "error": "No window focus backend (wmctrl/xdotool).", "window": target}


def open_application(name: str) -> dict[str, Any]:
    app = (name or "").strip()
    if not app:
        raise ValueError("name is required")
    # Prefer gtk-launch / gio / command on PATH
    if shutil.which("gtk-launch"):
        # desktop file id without .desktop
        r = _run(["gtk-launch", app if not app.endswith(".desktop") else app[:-8]], timeout=15)
        if r.get("ok"):
            return {"ok": True, "method": "gtk-launch", "name": app, **r}
    if shutil.which("gio"):
        r = _run(["gio", "launch", app] if app.endswith(".desktop") else ["gio", "open", app], timeout=15)
        if r.get("ok"):
            return {"ok": True, "method": "gio", "name": app, **r}
    which = shutil.which(app) or shutil.which(app.lower())
    if which:
        try:
            subprocess.Popen([which], start_new_session=True, env=clean_subprocess_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"ok": True, "method": "exec", "path": which, "name": app}
        except OSError as exc:
            return {"ok": False, "error": str(exc), "name": app}
    return {"ok": False, "error": f"Could not launch application {app!r}. Try full command or .desktop id.", "name": app}


def take_screenshot(path: str = "") -> dict[str, Any]:
    out = Path(path).expanduser() if path else _store("screenshots", f"observe-{int(time.time())}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("gnome-screenshot"):
        r = _run(["gnome-screenshot", "-f", str(out)])
        return {"ok": r.get("ok", out.exists()), "path": str(out), "backend": "gnome-screenshot", **r}
    if shutil.which("grim"):
        r = _run(["grim", str(out)])
        return {"ok": r.get("ok", out.exists()), "path": str(out), "backend": "grim", **r}
    if shutil.which("import"):
        r = _run(["import", "-window", "root", str(out)])
        return {"ok": r.get("ok", out.exists()), "path": str(out), "backend": "imagemagick", **r}
    try:
        import pyautogui

        pyautogui.screenshot(str(out))
        return {"ok": out.exists(), "path": str(out), "backend": "pyautogui"}
    except Exception as exc:
        return {"ok": False, "error": f"Screenshot failed: {exc}"}


def wait_for(query: str, timeout_s: float = 10.0, poll_s: float = 0.5) -> dict[str, Any]:
    deadline = time.time() + max(0.5, float(timeout_s))
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = find_window(query)
        if last.get("matches"):
            return {"ok": True, "waited_for": query, **last}
        time.sleep(max(0.1, float(poll_s)))
    return {"ok": False, "waited_for": query, "error": f"Timed out after {timeout_s}s waiting for {query!r}", **last}


def verify_window(query: str) -> dict[str, Any]:
    found = find_window(query)
    return {
        "ok": bool(found.get("matches")),
        "verified": bool(found.get("matches")),
        "query": query,
        "matches": found.get("matches", []),
    }


def accessibility_tree(max_nodes: int = 80) -> dict[str, Any]:
    """Best-effort AT-SPI tree via pyatspi (optional dependency)."""
    try:
        import pyatspi  # type: ignore
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "error": f"pyatspi not available ({exc}). Install python3-pyatspi for accessibility-based clicking.",
            "nodes": [],
        }
    nodes: list[dict[str, Any]] = []

    def walk(acc, depth: int = 0) -> None:
        if len(nodes) >= max(10, min(int(max_nodes), 300)):
            return
        try:
            name = acc.name or ""
            role = acc.getRoleName() if hasattr(acc, "getRoleName") else ""
            nodes.append({"name": name, "role": role, "depth": depth})
            for i in range(acc.childCount):
                try:
                    walk(acc.getChildAtIndex(i), depth + 1)
                except Exception:
                    continue
        except Exception:
            return

    try:
        desktop = pyatspi.Registry.getDesktop(0)
        walk(desktop)
        return {"ok": True, "available": True, "count": len(nodes), "nodes": nodes}
    except Exception as exc:
        return {"ok": False, "available": True, "error": str(exc), "nodes": nodes}


def find_accessible(name_query: str, max_nodes: int = 120) -> dict[str, Any]:
    q = (name_query or "").strip().lower()
    tree = accessibility_tree(max_nodes=max_nodes)
    if not tree.get("ok"):
        return tree
    matches = [n for n in tree.get("nodes", []) if q and q in str(n.get("name", "")).lower()]
    return {"ok": bool(matches), "query": name_query, "matches": matches[:20], "count": len(matches)}


def observe() -> dict[str, Any]:
    shot = take_screenshot()
    wins = list_windows()
    return {
        "ok": bool(shot.get("ok") or wins.get("ok")),
        "screenshot": shot,
        "windows": wins,
        "session": os.getenv("XDG_SESSION_TYPE", ""),
        "wayland_display": os.getenv("WAYLAND_DISPLAY", ""),
    }


def desktop_input_status() -> dict[str, Any]:
    """Combined readiness for Repair UI / API."""
    base = setup_wayland_input(start_daemon=False)
    uinput = Path("/dev/uinput")
    session = os.getenv("XDG_SESSION_TYPE", "").strip().lower() or "unknown"
    return {
        "ok": bool(base.get("ready")),
        "ready": bool(base.get("ready")),
        "session": session,
        "wayland": session == "wayland" or bool(os.getenv("WAYLAND_DISPLAY")),
        "ydotool": shutil.which("ydotool") or "",
        "ydotoold": shutil.which("ydotoold") or "",
        "uinput_exists": uinput.exists(),
        "uinput_writable": uinput.exists() and os.access(uinput, os.W_OK),
        "socket": base.get("YDOTOOL_SOCKET") or "",
        "install_script": base.get("install_script") or "",
        "message": base.get("message") or "",
        "zero_fallback": "Use install_zero_computer + zero_computer tools, or native desktop_* tools after setup.",
    }


def install_wayland_input_elevated() -> dict[str, Any]:
    """Run the generated install script with pkexec/sudo when possible; always refresh daemon."""
    prepared = setup_wayland_input(start_daemon=True)
    script = Path(str(prepared.get("install_script") or ""))
    if not script.is_file():
        return {"ok": False, "message": "Install script missing; call desktop_setup_input first.", **prepared}

    elevated = {"ok": False, "method": None, "detail": ""}
    if platform.system() == "Linux":
        # Prefer pkexec (GUI password prompt), then sudo -n, then plain sudo
        attempts: list[list[str]] = []
        if shutil.which("pkexec"):
            attempts.append(["pkexec", "bash", str(script)])
        if shutil.which("sudo"):
            attempts.append(["sudo", "-n", "bash", str(script)])
            attempts.append(["sudo", "bash", str(script)])
        last_err = ""
        for cmd in attempts:
            r = _run(cmd, timeout=90)
            elevated = {"ok": bool(r.get("ok")), "method": " ".join(cmd[:2]), "detail": (r.get("stderr") or r.get("stdout") or "")[:2000], "returncode": r.get("returncode")}
            if r.get("ok"):
                break
            last_err = elevated["detail"]
        if not elevated.get("ok"):
            elevated["message"] = (
                "Could not elevate automatically. Run manually: sudo bash " + str(script)
                + (f" ({last_err[:200]})" if last_err else "")
            )
    else:
        elevated = {"ok": True, "method": "n/a", "message": "Non-Linux: no uinput rule needed."}

    # Retry daemon after rules (may still need re-login for group)
    refreshed = setup_wayland_input(start_daemon=True)
    status = desktop_input_status()
    return {
        "ok": bool(status.get("ready") or elevated.get("ok")),
        "elevated": elevated,
        "status": status,
        "refreshed": refreshed,
        "message": status.get("message") if status.get("ready") else (
            elevated.get("message") or status.get("message") or "Desktop input setup attempted."
        ),
    }


def register_desktop_agent_tools(mcp) -> None:
    from mcp.server.fastmcp import FastMCP
    from dana.tools.mcp_quality import MUTATING, READ_ONLY, actionable_error

    # Import low-level desktop_control path lazily via local_agent helpers when needed
    def _input(action: str, **kwargs):
        from dana.tools import local_agent as la
        # Reuse desktop_control logic by calling internal pieces
        # Prefer calling through the same backend functions
        system = platform.system()
        if action in {"move", "click", "type", "key", "hotkey", "scroll", "move_relative", "double_click", "right_click"}:
            if system == "Linux":
                try:
                    backend = la._desktop_backend()
                except Exception as exc:
                    raise RuntimeError(actionable_error(str(exc), next_steps=["Call desktop_agent setup_input", "Install ydotool/ydotoold"])) from exc
                if backend == "ydotool" and action in {"move", "move_relative", "click", "scroll", "type", "key", "hotkey"}:
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
                if action == "double_click":
                    return la._desktop_ydo("click", int(kwargs.get("x", 0)), int(kwargs.get("y", 0)), "left", 2, 0, "", "") if backend == "ydotool" else None
                if action == "right_click":
                    return la._desktop_ydo("click", int(kwargs.get("x", 0)), int(kwargs.get("y", 0)), "right", 1, 0, "", "") if backend == "ydotool" else None
        # Fall back to invoking desktop_control tool function is hard; use pyautogui last resort
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError("No input backend available") from exc
        x, y = int(kwargs.get("x", 0)), int(kwargs.get("y", 0))
        if action == "move":
            pyautogui.moveTo(max(0, x), max(0, y)); return {"ok": True, "backend": "pyautogui"}
        if action == "click":
            pyautogui.click(x=max(0, x), y=max(0, y), clicks=int(kwargs.get("clicks", 1)), button=kwargs.get("button", "left")); return {"ok": True}
        if action == "double_click":
            pyautogui.doubleClick(x=max(0, x), y=max(0, y)); return {"ok": True}
        if action == "right_click":
            pyautogui.click(x=max(0, x), y=max(0, y), button="right"); return {"ok": True}
        if action == "type":
            pyautogui.write(str(kwargs.get("text", "")), interval=0.001); return {"ok": True}
        if action == "key":
            pyautogui.press(str(kwargs.get("key", ""))); return {"ok": True}
        if action == "hotkey":
            parts = [p.strip().lower() for p in str(kwargs.get("key", "")).replace("+", " ").split() if p.strip()]
            pyautogui.hotkey(*parts); return {"ok": True}
        raise ValueError(f"Unsupported input action: {action}")

    @mcp.tool(annotations=READ_ONLY("Desktop observe"))
    def desktop_observe() -> dict:
        """Capture screenshot + window list without injecting input (observation plane)."""
        return observe()

    @mcp.tool(annotations=MUTATING("Setup Wayland input"))
    def desktop_setup_input(start_daemon: bool = True) -> dict:
        """Prepare ydotool/uinput helpers and try to start ydotoold for Wayland input."""
        return setup_wayland_input(start_daemon=start_daemon)

    @mcp.tool(annotations=MUTATING("Install Wayland input (elevated)"))
    def desktop_install_input() -> dict:
        """Install udev/uinput rules via pkexec/sudo and restart ydotoold when possible."""
        return install_wayland_input_elevated()

    @mcp.tool(annotations=READ_ONLY("Desktop input status"))
    def desktop_input_status_tool() -> dict:
        """Report ydotool/uinput readiness for Repair UI and agents."""
        return desktop_input_status()

    @mcp.tool(annotations=MUTATING("Open application"))
    def desktop_open_app(name: str, wait_timeout_s: float = 8.0) -> dict:
        """Launch an application by name/desktop-id, then wait briefly for a matching window."""
        launched = open_application(name)
        waited = wait_for(name, timeout_s=wait_timeout_s) if launched.get("ok") else {"ok": False}
        return {"ok": bool(launched.get("ok")), "launch": launched, "window": waited}

    @mcp.tool(annotations=MUTATING("Focus application window"))
    def desktop_focus_app(query: str) -> dict:
        """Focus a window by title substring or id (wmctrl/xdotool)."""
        return focus_window(query)

    @mcp.tool(annotations=READ_ONLY("Find window"))
    def desktop_find_window(query: str) -> dict:
        """Find windows matching a title substring."""
        return find_window(query)

    @mcp.tool(annotations=READ_ONLY("Wait for window"))
    def desktop_wait_for(query: str, timeout_s: float = 10.0, poll_s: float = 0.5) -> dict:
        """Poll until a window title matches query or timeout."""
        return wait_for(query, timeout_s=timeout_s, poll_s=poll_s)

    @mcp.tool(annotations=READ_ONLY("Verify window visible"))
    def desktop_verify(query: str, screenshot: bool = False) -> dict:
        """Verify a window is present; optionally take a screenshot for the agent."""
        result = verify_window(query)
        if screenshot:
            result["screenshot"] = take_screenshot()
        return result

    @mcp.tool(annotations=MUTATING("Click UI element by name"))
    def desktop_click_element(name: str, button: str = "left", verify: bool = True) -> dict:
        """Focus/find a window or accessible node by name, then click center of window bounds when possible.

        On Wayland without AT-SPI geometry, focuses the matching window (title) as best effort.
        Prefer accessibility (pyatspi) when installed for true element names.
        """
        acc = find_accessible(name)
        focused = focus_window(name)
        click_result = None
        # If wmctrl gave geometry, click center
        matches = focused.get("window") or (focused.get("matches") or [None])[0]
        if isinstance(matches, dict) and matches.get("w") and matches.get("h"):
            cx = int(matches["x"]) + int(matches["w"]) // 2
            cy = int(matches["y"]) + int(matches["h"]) // 2
            try:
                click_result = _input("click", x=cx, y=cy, button=button, clicks=1)
            except Exception as exc:
                click_result = {"ok": False, "error": str(exc)}
        verified = verify_window(name) if verify else None
        return {
            "ok": bool(focused.get("ok") or (click_result or {}).get("ok")),
            "accessibility": acc,
            "focus": focused,
            "click": click_result,
            "verify": verified,
            "hint": "For true element-level clicks install python3-pyatspi; geometry click uses window bounds from wmctrl.",
        }

    @mcp.tool(annotations=MUTATING("Type into focused UI"))
    def desktop_type_into(text: str, submit: bool = False, verify_query: str = "") -> dict:
        """Type text into the currently focused control; optional Enter and post-verify."""
        typed = _input("type", text=text)
        submitted = None
        if submit:
            submitted = _input("key", key="Return")
        verified = verify_window(verify_query) if verify_query else None
        return {"ok": bool(typed.get("ok", True)), "type": typed, "submit": submitted, "verify": verified}

    @mcp.tool(annotations=MUTATING("Press shortcut"))
    def desktop_press_shortcut(keys: str) -> dict:
        """Press a hotkey chord such as ctrl+c or alt+Tab."""
        return _input("hotkey", key=keys)

    @mcp.tool(annotations=MUTATING("Desktop action with verify"))
    def desktop_act(
        action: str,
        query: str = "",
        text: str = "",
        x: int = 0,
        y: int = 0,
        verify_query: str = "",
        screenshot_after: bool = False,
    ) -> dict:
        """High-level plan step: open|focus|click|type|hotkey|wait then optional verify + screenshot."""
        action = (action or "").strip().lower()
        result: dict[str, Any] = {"action": action}
        if action == "open":
            result["result"] = open_application(query or text)
            if result["result"].get("ok") and (verify_query or query):
                result["wait"] = wait_for(verify_query or query, timeout_s=8)
        elif action == "focus":
            result["result"] = focus_window(query or text)
        elif action == "wait":
            result["result"] = wait_for(query or text)
        elif action == "click":
            result["result"] = _input("click", x=x, y=y)
        elif action == "type":
            result["result"] = _input("type", text=text)
        elif action in {"hotkey", "shortcut"}:
            result["result"] = _input("hotkey", key=query or text)
        elif action == "observe":
            result["result"] = observe()
        else:
            raise ValueError("action must be open, focus, wait, click, type, hotkey, or observe")
        if verify_query:
            result["verify"] = verify_window(verify_query)
        if screenshot_after:
            result["screenshot"] = take_screenshot()
        ok = True
        if isinstance(result.get("result"), dict) and "ok" in result["result"]:
            ok = bool(result["result"]["ok"])
        if isinstance(result.get("verify"), dict) and "ok" in result["verify"]:
            ok = ok and bool(result["verify"]["ok"])
        result["ok"] = ok
        return result

    @mcp.tool(annotations=READ_ONLY("Accessibility tree probe"))
    def desktop_accessibility(max_nodes: int = 80) -> dict:
        """Dump AT-SPI accessible names/roles when python3-pyatspi is installed."""
        return accessibility_tree(max_nodes=max_nodes)
