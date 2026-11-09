#!/usr/bin/env python3
"""Apply App.tsx whip dock + imports."""
from pathlib import Path

p = Path("ui/src/App.tsx")
t = p.read_text(encoding="utf-8")
changed = False

old_imp = 'import { playOpenWhipCrack } from "./whipAssets";'
new_imp = 'import { playOpenWhipCrack, getWhipVolume, setWhipVolume, isWhipMuted, setWhipMuted } from "./whipAssets";'
if old_imp in t:
    t = t.replace(old_imp, new_imp)
    changed = True
    print("import")

if "whipVol" not in t and "const [whipArmed, setWhipArmed] = useState(false);" in t:
    t = t.replace(
        "  const [whipArmed, setWhipArmed] = useState(false);",
        "  const [whipArmed, setWhipArmed] = useState(false);\n"
        "  const [whipVol, setWhipVolState] = useState(() => Math.round(getWhipVolume() * 100));\n"
        "  const [whipMuted, setWhipMutedState] = useState(() => isWhipMuted());",
    )
    changed = True
    print("state")

old_fab = (
    '      <button\n'
    '        type="button"\n'
    '        className={"whip-fab" + (whipArmed ? " armed" : "") + (whipLevel > 0 ? " boosted" : "")}'
)
new_fab = (
    '      <div className="whip-dock">\n'
    '        <div className="whip-audio-pill glass" title="Whip crack sound volume">\n'
    '          <button\n'
    '            type="button"\n'
    '            className="whip-mute-btn"\n'
    '            aria-label={whipMuted ? "Unmute whip sound" : "Mute whip sound"}\n'
    '            onClick={() => {\n'
    '              const next = !whipMuted;\n'
    '              setWhipMuted(next);\n'
    '              setWhipMutedState(next);\n'
    '              if (!next && whipVol === 0) {\n'
    '                setWhipVolume(0.85);\n'
    '                setWhipVolState(85);\n'
    '              }\n'
    '            }}\n'
    '          >\n'
    '            {whipMuted || whipVol === 0 ? "🔇" : whipVol < 45 ? "🔉" : "🔊"}\n'
    '          </button>\n'
    '          <input\n'
    '            type="range"\n'
    '            min={0}\n'
    '            max={100}\n'
    '            value={whipMuted ? 0 : whipVol}\n'
    '            aria-label="Whip sound volume"\n'
    '            onChange={(e) => {\n'
    '              const v = Number(e.target.value);\n'
    '              setWhipVolState(v);\n'
    '              setWhipMutedState(v === 0);\n'
    '              setWhipMuted(v === 0);\n'
    '              setWhipVolume(v / 100);\n'
    '            }}\n'
    '          />\n'
    '          <span className="whip-vol-label">{whipMuted ? "Mute" : `${whipVol}%`}</span>\n'
    '        </div>\n'
    '        <button\n'
    '        type="button"\n'
    '        className={"whip-fab" + (whipArmed ? " armed" : "") + (whipLevel > 0 ? " boosted" : "")}'
)
if old_fab in t and 'className="whip-dock"' not in t:
    t = t.replace(old_fab, new_fab, 1)
    pat = '{whipLevel > 0 ? <span className="whip-level-badge">{whipLevel}</span> : null}\n      </button>'
    if pat in t:
        t = t.replace(
            pat,
            '{whipLevel > 0 ? <span className="whip-level-badge">{whipLevel}</span> : null}\n'
            '        </button>\n'
            '      </div>',
            1,
        )
    changed = True
    print("dock")

if changed:
    p.write_text(t, encoding="utf-8")
    print("wrote App.tsx")
else:
    print("App.tsx already patched or patterns missing")
