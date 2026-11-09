#!/usr/bin/env python3
"""Apply Dana 1.8 FLClash UI structure on top of existing App.tsx."""
from pathlib import Path
import re

app = Path("ui/src/App.tsx")
t = app.read_text(encoding="utf-8")

t2 = re.sub(r'import logo from "[^"]+";', 'import logo from "./assets/dana-logo.svg";', t, count=1)
if t2 != t:
    t = t2
    print("logo")

if 'import "./flclash.css"' not in t and 'import "./App.css"' in t:
    t = t.replace('import "./App.css";', 'import "./App.css";\nimport "./flclash.css";')
    print("flclash css import")

if 'useState("Dashboard")' not in t:
    t = t.replace('const [view, setView] = useState("Setup");', 'const [view, setView] = useState("Dashboard");')

if "settingsTab" not in t and 'useState("Dashboard")' in t:
    t = t.replace(
        'const [view, setView] = useState("Dashboard");',
        'const [view, setView] = useState("Dashboard");\n'
        '  const [settingsTab, setSettingsTab] = useState<"Config" | "Skills" | "Repair" | "Usage" | "Help">("Config");\n'
        '  const [endpointMode, setEndpointMode] = useState<"all" | "local" | "public" | "supermcp">("all");',
    )
    print("state")

if 'id: "Setup"' in t and 'id: "Dashboard"' not in t:
    t2 = re.sub(
        r"const navItems: \{.*?\];",
        """const navItems: {
    id: \"Dashboard\" | \"Network\" | \"Logs\" | \"Settings\";
    label: string;
    icon: string;
  }[] = [
    { id: \"Dashboard\", label: \"Dashboard\", icon: \"setup\" },
    { id: \"Network\", label: \"Network\", icon: \"control\" },
    { id: \"Logs\", label: \"Logs\", icon: \"logs\" },
    { id: \"Settings\", label: \"Settings\", icon: \"config\" },
  ];

  const settingsItems: { id: \"Config\" | \"Skills\" | \"Repair\" | \"Usage\" | \"Help\"; label: string; icon: string }[] = [
    { id: \"Config\", label: \"Configuration\", icon: \"config\" },
    { id: \"Skills\", label: \"Skills\", icon: \"skills\" },
    { id: \"Repair\", label: \"Repair\", icon: \"repair\" },
    { id: \"Usage\", label: \"Usage\", icon: \"usage\" },
    { id: \"Help\", label: \"Guide\", icon: \"help\" },
  ];""",
        t,
        count=1,
        flags=re.S,
    )
    if t2 != t:
        t = t2
        print("nav")

for a, b in [
    ('view === "Setup"', 'view === "Dashboard"'),
    ('view === "Control"', 'view === "Network"'),
    ('setView("Control")', 'setView("Network")'),
    ('setView("Setup")', 'setView("Dashboard")'),
]:
    if a in t:
        t = t.replace(a, b)
        print("map", a)

if 'settingsTab === "Config"' not in t:
    for name in ("Config", "Repair", "Help", "Usage", "Skills"):
        t = t.replace(f'view === "{name}"', f'(view === "Settings" && settingsTab === "{name}")')
    print("settings gate")

app.write_text(t, encoding="utf-8")
print("done", len(t))
