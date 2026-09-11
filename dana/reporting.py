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
REPORT_DIR = ROOT / ".dana"
REPORT_JSON = REPORT_DIR / "report.json"
# Keep the stable report at the project root for backwards compatibility.
# Temporary atomic-write files are stored under .dana and never beside source files.
REPORT_HTML = ROOT / "report.html"
_LOCK = threading.Lock()
MAX_EVENTS = 1000


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use one dedicated runtime temp directory for every report write. This
    # prevents .report-* artifacts from ever appearing beside the source tree.
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
    try:
        data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        data = {}
    data.setdefault("start", time.time())
    data.setdefault("last", None)
    data.setdefault("input", 0)
    data.setdefault("output", 0)
    data.setdefault("operations", 0)
    data.setdefault("exact_tokens", 0)
    data.setdefault("estimated_tokens", 0)
    data.setdefault("events", [])
    return data


def _render(data: dict) -> str:
    events = data["events"]
    total = int(data["input"]) + int(data["output"])
    now = time.time()
    elapsed = (data["last"] or now) - data["start"]

    tools = Counter(str(e.get("tool", "unknown")) for e in events)
    workers = Counter(str(e.get("worker", "unknown")) for e in events)
    durations = [float(e.get("duration", 0)) for e in events]
    successes = sum(1 for e in events if e.get("success"))
    success_rate = (successes / len(events) * 100) if events else 100.0
    avg_duration = (sum(durations) / len(durations)) if durations else 0.0

    buckets = defaultdict(lambda: {"input": 0, "output": 0})
    for event in events:
        label = time.strftime("%H:%M", time.localtime(event["time"]))
        buckets[label]["input"] += int(event.get("input", 0))
        buckets[label]["output"] += int(event.get("output", 0))
    chart = [{"label": key, **value} for key, value in list(buckets.items())[-48:]]

    rows = []
    for event in reversed(events[-100:]):
        status = "✓ DONE" if event.get("success") else "✗ FAILED"
        rows.append(
            "<tr>"
            f"<td>{html.escape(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event['time'])))}</td>"
            f"<td>{html.escape(str(event.get('worker', '')))} #{int(event.get('number', 0))}</td>"
            f"<td><code>{html.escape(str(event.get('tool', '')))}</code></td>"
            f"<td>{int(event.get('input', 0)):,}</td>"
            f"<td>{int(event.get('output', 0)):,}</td>"
            f"<td>{int(event.get('input', 0)) + int(event.get('output', 0)):,}</td>"
            f"<td>{float(event.get('duration', 0)):.0f} ms</td>"
            f"<td class=\"{'ok' if event.get('success') else 'fail'}\">{status}</td>"
            f"<td>{html.escape(str(event.get('source', 'estimate')))}</td>"
            "</tr>"
        )

    tool_rows = "".join(
        f"<tr><td><code>{html.escape(name)}</code></td><td>{count:,}</td></tr>"
        for name, count in tools.most_common(10)
    ) or "<tr><td colspan=\"2\">No activity yet</td></tr>"

    chart_json = json.dumps(chart, ensure_ascii=False)
    updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data["last"] or now))
    started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data["start"]))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dana Usage Report</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;background:#07111f;color:#e8f0fb;font:14px Inter,system-ui,sans-serif}}main{{max-width:1400px;margin:auto;padding:28px}}h1{{margin:0;font-size:30px}}h2{{margin:28px 0 12px}}.sub{{color:#94a8c2;margin-top:8px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:22px 0}}.card,.panel{{background:#0d1b2d;border:1px solid #1c324b;border-radius:14px;padding:18px}}.label{{color:#8ea3be;font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.value{{font-size:28px;font-weight:750;margin-top:7px}}.two{{display:grid;grid-template-columns:2fr 1fr;gap:14px}}canvas{{width:100%;height:300px;background:#091624;border-radius:10px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #1c324b;text-align:left;white-space:nowrap}}th{{color:#8ea3be;font-size:12px}}.scroll{{overflow:auto}}code{{color:#b7d7ff}}.ok{{color:#64d9a4}}.fail{{color:#ff7f91}}footer{{color:#7086a1;margin:20px 0;font-size:12px}}
</style></head><body><main>
<h1>Dana Usage Report</h1><div class="sub">Started: {started} · Last activity: {updated} · Auto-updated after every tool execution</div>
<div class="grid">
<div class="card"><div class="label">Total tokens</div><div class="value">{total:,}</div></div>
<div class="card"><div class="label">Input tokens</div><div class="value">{int(data["input"]):,}</div></div>
<div class="card"><div class="label">Output tokens</div><div class="value">{int(data["output"]):,}</div></div>
<div class="card"><div class="label">Operations</div><div class="value">{int(data["operations"]):,}</div></div>
<div class="card"><div class="label">Success rate</div><div class="value">{success_rate:.1f}%</div></div>
<div class="card"><div class="label">Usage time</div><div class="value">{_fmt_duration(elapsed)}</div></div>
</div>
<div class="two"><section class="panel"><h2>Token activity</h2><canvas id="chart" width="1100" height="300"></canvas></section>
<section class="panel"><h2>Top tools</h2><div class="scroll"><table><tr><th>Tool</th><th>Calls</th></tr>{tool_rows}</table></div><h2>Workers</h2><div class="sub">{html.escape(", ".join(f"{name}: {count}" for name,count in workers.most_common()) or "No activity yet")}</div><h2>Average duration</h2><div class="value">{avg_duration:.0f} ms</div></section></div>
<section class="panel"><h2>Recent operations</h2><div class="scroll"><table><tr><th>Time</th><th>Worker</th><th>Tool</th><th>Input</th><th>Output</th><th>Total</th><th>Duration</th><th>Status</th><th>Source</th></tr>{"".join(rows) or "<tr><td colspan='9'>No operations yet</td></tr>"}</table></div></section>
<footer>Exact = provider-reported usage. Estimated = Dana tokenizer estimate. Runtime data and this report are local and ignored by Git.</footer>
</main><script>
const points={chart_json},c=document.getElementById('chart'),ctx=c.getContext('2d'),W=c.width,H=c.height,p=38,max=Math.max(1,...points.map(x=>x.input+x.output));ctx.clearRect(0,0,W,H);ctx.strokeStyle='#29435e';ctx.beginPath();ctx.moveTo(p,18);ctx.lineTo(p,H-p);ctx.lineTo(W-18,H-p);ctx.stroke();if(points.length){{const draw=(key,offset)=>{{ctx.strokeStyle=key==='input'?'#62a8ff':'#65d8a0';ctx.beginPath();points.forEach((v,i)=>{{const x=p+(W-p-25)*i/Math.max(points.length-1,1),y=H-p-(H-p-35)*(v[key]+offset)/max;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}});ctx.stroke()}};draw('input',0);draw('output',0)}}
</script></body></html>"""


def update_report(tool: str, worker: str, number: int, input_tokens: int, output_tokens: int, duration_ms: float, success: bool, exact: bool = False, source: str = "estimate") -> None:
    with _LOCK:
        REPORT_DIR.mkdir(exist_ok=True)
        data = _load()
        inp, out = max(0, int(input_tokens)), max(0, int(output_tokens))
        now = time.time()
        data["last"] = now
        data["input"] += inp
        data["output"] += out
        data["operations"] += 1
        if exact:
            data["exact_tokens"] += inp + out
        else:
            data["estimated_tokens"] += inp + out
        data["events"].append({"time": now, "worker": worker, "number": number, "tool": tool, "input": inp, "output": out, "duration": duration_ms, "success": success, "exact": exact, "source": source})
        data["events"] = data["events"][-MAX_EVENTS:]
        _atomic_write(REPORT_JSON, json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        _atomic_write(REPORT_HTML, _render(data))
