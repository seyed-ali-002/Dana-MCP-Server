from __future__ import annotations

import html
import json
import os
import tempfile
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _persistent_report_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "Dana" / "reports"
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg) / "dana" / "reports"
    return Path.home() / ".config" / "dana" / "reports"

REPORT_DIR = _persistent_report_dir()
REPORT_JSON = REPORT_DIR / "report.json"
REPORT_HTML = REPORT_DIR / "report.html"
LEGACY_REPORT_JSON = ROOT / ".dana" / "report.json"
LEGACY_REPORT_HTML = ROOT / "report.html"
_LOCK = threading.Lock()
MAX_EVENTS = 1000


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = REPORT_DIR
    fd, tmp = tempfile.mkstemp(prefix=".report-", dir=temp_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _load() -> dict:
    data = {}
    for candidate in (REPORT_JSON, LEGACY_REPORT_JSON):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            break
        except (OSError, ValueError, TypeError):
            continue
    data.setdefault("start", time.time())
    data.setdefault("last", None)
    data.setdefault("input", 0)
    data.setdefault("output", 0)
    data.setdefault("operations", 0)
    data.setdefault("active_seconds", 0.0)
    data.setdefault("exact_tokens", 0)
    data.setdefault("estimated_tokens", 0)
    data.setdefault("events", [])
    return data


def update_report(tool: str, worker: str, number: int, input_tokens: int, output_tokens: int, duration_ms: float, success: bool, exact: bool = False, source: str = "estimate", detail: dict | None = None) -> None:
    with _LOCK:
        REPORT_DIR.mkdir(exist_ok=True)
        data = _load()
        inp, out = max(0, int(input_tokens)), max(0, int(output_tokens))
        now = time.time()
        data["last"] = now
        data["input"] += inp
        data["output"] += out
        data["operations"] += 1
        data["active_seconds"] += max(0.0, float(duration_ms)) / 1000.0
        if exact:
            data["exact_tokens"] += inp + out
        else:
            data["estimated_tokens"] += inp + out
        event = {"time": now, "started": now - max(0.0, float(duration_ms)) / 1000.0, "worker": worker, "number": number, "tool": tool, "input": inp, "output": out, "duration": duration_ms, "success": success, "exact": exact, "source": source}
        if isinstance(detail, dict):
            for key in ("args", "result", "error", "line"):
                val = detail.get(key)
                if val:
                    event[key] = str(val)[:2000]
        data["events"].append(event)
        data["events"] = data["events"][-MAX_EVENTS:]
        _atomic_write(REPORT_JSON, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        try:
            _atomic_write(REPORT_HTML, _render(data))
        except Exception:
            pass


def _render(data: dict) -> str:
    events = list(data.get("events") or [])
    tools = Counter(str(e.get("tool") or "?") for e in events)
    workers = Counter(str(e.get("worker") or "?") for e in events)
    started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(data.get("start") or time.time())))
    updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(data.get("last") or time.time()))) if data.get("last") else "—"
    total = int(data.get("input") or 0) + int(data.get("output") or 0)
    ops = max(1, int(data.get("operations") or 0))
    success_rate = 100.0 * sum(1 for e in events if e.get("success")) / max(1, len(events))
    elapsed = float(data.get("active_seconds") or 0)
    avg_duration = sum(float(e.get("duration") or 0) for e in events) / max(1, len(events))
    tool_rows = "".join(f"<tr><td>{html.escape(str(n))}</td><td>{c}</td></tr>" for n, c in tools.most_common(20))
    rows = []
    for e in reversed(events[-40:]):
        rows.append(
            "<tr>"
            f"<td>{html.escape(time.strftime('%H:%M:%S', time.localtime(float(e.get('time') or 0))))}</td>"
            f"<td>{html.escape(str(e.get('worker') or ''))}</td>"
            f"<td>{html.escape(str(e.get('tool') or ''))}</td>"
            f"<td>{int(e.get('input') or 0)}</td>"
            f"<td>{int(e.get('output') or 0)}</td>"
            f"<td>{int(e.get('input') or 0)+int(e.get('output') or 0)}</td>"
            f"<td>{float(e.get('duration') or 0):.0f}</td>"
            f"<td>{'ok' if e.get('success') else 'fail'}</td>"
            f"<td>{html.escape(str(e.get('source') or ''))}</td>"
            "</tr>"
        )
    chart = [{"input": int(e.get("input") or 0), "output": int(e.get("output") or 0)} for e in events[-60:]]
    chart_json = json.dumps(chart)
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Dana Usage</title>
<style>body{{font-family:system-ui;background:#0b1220;color:#e8eef7;margin:0;padding:24px}} .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}} .card,.panel{{background:#121a2b;border:1px solid #243148;border-radius:12px;padding:14px}} .label{{color:#8fa3bf;font-size:12px}} .value{{font-size:22px;font-weight:700}} table{{width:100%;border-collapse:collapse}} td,th{{padding:6px;border-bottom:1px solid #243148;text-align:left;font-size:12px}} .scroll{{max-height:320px;overflow:auto}}</style></head><body>
<main><h1>Dana Usage Report</h1><div class='label'>Started: {started} · Last: {updated}</div>
<div class='grid'>
<div class='card'><div class='label'>Total tokens</div><div class='value'>{total:,}</div></div>
<div class='card'><div class='label'>Operations</div><div class='value'>{ops}</div></div>
<div class='card'><div class='label'>Success</div><div class='value'>{success_rate:.1f}%</div></div>
</div>
<section class='panel'><h2>Recent</h2><div class='scroll'><table><tr><th>Time</th><th>Worker</th><th>Tool</th><th>In</th><th>Out</th><th>Total</th><th>ms</th><th>Status</th><th>Source</th></tr>{''.join(rows)}</table></div></section>
</main></body></html>"""
