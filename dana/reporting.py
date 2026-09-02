from __future__ import annotations

import html
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".dana"
REPORT_JSON = REPORT_DIR / "report.json"
REPORT_HTML = ROOT / "report.html"
_LOCK = threading.Lock()

def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".report-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def update_report(tool: str, worker: str, number: int, input_tokens: int, output_tokens: int, duration_ms: float, success: bool, exact: bool = False, source: str = "estimate") -> None:
    with _LOCK:
        REPORT_DIR.mkdir(exist_ok=True)
        try:
            data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {"start": time.time(), "last": None, "input": 0, "output": 0, "operations": 0, "exact_tokens": 0, "estimated_tokens": 0, "events": []}
        # Reports created by older Dana versions may not have the newer
        # aggregate fields. Migrate them in memory instead of allowing the
        # reporting path to break the actual tool invocation.
        data.setdefault("start", time.time())
        data.setdefault("last", None)
        data.setdefault("input", 0)
        data.setdefault("output", 0)
        data.setdefault("operations", 0)
        data.setdefault("exact_tokens", 0)
        data.setdefault("estimated_tokens", 0)
        data.setdefault("events", [])
        inp, out = max(0, int(input_tokens)), max(0, int(output_tokens))
        now = time.time()
        data["last"] = now; data["input"] += inp; data["output"] += out; data["operations"] += 1
        data["exact_tokens"] += inp + out if exact else 0
        data["estimated_tokens"] += 0 if exact else inp + out
        data["events"].append({"time": now, "worker": worker, "number": number, "tool": tool, "input": inp, "output": out, "duration": duration_ms, "success": success, "exact": exact, "source": source})
        data["events"] = data["events"][-1000:]
        _atomic_write(REPORT_JSON, json.dumps(data, ensure_ascii=False))
        rows = "".join("<tr><td>{}</td><td>{} #{}</td><td>{}</td><td>{:,}</td><td>{:,}</td><td>{:,}</td><td>{:.0f}ms</td><td>{}</td><td>{}</td></tr>".format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e["time"])), html.escape(str(e["worker"])), e["number"], html.escape(str(e["tool"])), e["input"], e["output"], e["input"]+e["output"], e["duration"], "DONE" if e["success"] else "FAIL", html.escape(str(e["source"]))) for e in reversed(data["events"]))
        points = json.dumps([{"t": time.strftime("%H:%M", time.localtime(e["time"])), "v": e["input"] + e["output"]} for e in data["events"][-60:]])
        total = data["input"] + data["output"]
        page = """<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>Dana Usage Report</title><style>body{font:15px system-ui;background:#08111f;color:#eee;padding:28px;max-width:1300px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.card{background:#101d30;padding:18px;border-radius:12px}.num{font-size:28px;font-weight:700;margin-top:6px}.muted{color:#9fb0c5}table{width:100%;border-collapse:collapse;margin-top:18px}td,th{padding:8px;border-bottom:1px solid #263b55;text-align:left}canvas{width:100%;height:280px;background:#0d1929;border-radius:12px;margin-top:18px}</style></head><body><h1>Dana Usage Report</h1><p class="muted">Live report. Provider-reported usage is exact; local tokenizer values are estimates.</p><div class="grid"><div class="card">TOTAL TOKENS<div class="num">{total:,}</div></div><div class="card">INPUT<div class="num">{inp:,}</div></div><div class="card">OUTPUT<div class="num">{out:,}</div></div><div class="card">EXACT<div class="num">{exact:,}</div></div><div class="card">ESTIMATED<div class="num">{estimated:,}</div></div><div class="card">OPERATIONS<div class="num">{ops:,}</div></div></div><canvas id="chart" width=1200 height=280></canvas><h2>Recent operations</h2><table><tr><th>Time</th><th>Worker</th><th>Tool</th><th>Input</th><th>Output</th><th>Total</th><th>Duration</th><th>Status</th><th>Source</th></tr>{rows}</table><script>const p={points},c=document.getElementById('chart'),x=c.getContext('2d'),w=c.width,h=c.height,m=35,max=Math.max(...p.map(a=>a.v),1);x.strokeStyle='#38506c';x.beginPath();x.moveTo(m,15);x.lineTo(m,h-m);x.lineTo(w-m,h-m);x.stroke();if(p.length){x.strokeStyle='#5ee6a8';x.beginPath();p.forEach((a,i)=>{const X=m+(w-2*m)*i/Math.max(p.length-1,1),Y=h-m-(h-2*m)*a.v/max;i?x.lineTo(X,Y):x.moveTo(X,Y)});x.stroke()}</script></body></html>"""
        # Do not use str.format() here: the inline CSS/JavaScript contains
        # many literal braces. Placeholder replacement keeps those braces
        # literal and prevents report generation from raising KeyError.
        for key, value in {
            "total:": f"{total:,}",
            "inp": f"{data['input']:,}",
            "out": f"{data['output']:,}",
            "exact": f"{data['exact_tokens']:,}",
            "estimated": f"{data['estimated_tokens']:,}",
            "ops": f"{data['operations']:,}",
            "rows": rows,
            "points": points,
        }.items():
            page = page.replace("{" + key + "}", value)
        _atomic_write(REPORT_HTML, page)
