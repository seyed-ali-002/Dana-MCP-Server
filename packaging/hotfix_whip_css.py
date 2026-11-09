#!/usr/bin/env python3
from pathlib import Path
p = Path("ui/src/App.css")
t = p.read_text(encoding="utf-8")
if ".whip-dock {" in t:
    print("css already")
    raise SystemExit(0)
css = r'''
/* --- Visual Polish & Whip Audio Dock ------------------------------------- */
.whip-dock {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 95;
  display: flex;
  align-items: center;
  gap: 10px;
}

.whip-dock .whip-fab {
  position: relative;
  right: auto;
  bottom: auto;
  flex-shrink: 0;
}

.whip-audio-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface) 90%, var(--bg));
  border: 1px solid var(--border-strong);
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
}

.whip-mute-btn {
  font-size: 15px;
  line-height: 1;
  padding: 4px;
  border-radius: 50%;
  display: grid;
  place-items: center;
}

.whip-audio-pill input[type="range"] {
  width: 78px;
  accent-color: var(--accent);
  cursor: pointer;
}

.whip-vol-label {
  font-size: 11px;
  font-weight: 600;
  font-family: var(--mono);
  color: var(--muted);
  min-width: 34px;
  text-align: right;
}

.card,
.glass,
.connections-panel,
.logs-panel,
.hero {
  backdrop-filter: blur(14px);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.card:hover,
.connections-panel:hover,
.logs-panel:hover {
  border-color: color-mix(in srgb, var(--accent) 26%, var(--border-strong));
}
'''
p.write_text(t.rstrip() + "\n" + css + "\n", encoding="utf-8")
print("css appended")
