# 20 — Computer Use (Claude-style agent loop)

## Goal
Let Dana drive real GUIs (DaVinci, GIMP, IDEs, …) via **observe → act → verify**, not only raw `click(x,y)`.

## Tool surface
| Tool | Role |
|------|------|
| `computer_observe` | Composite state + screenshot (+ region crop) |
| `computer_act` | open_app / focus / click / type / hotkey / … + verify |
| `computer_wait` | window:Title, text:OCR, screen_changed, input_ready |
| `computer_locate_text` | tesseract OCR boxes |
| `computer_agent_step` | Observation + history + planner hints |
| `computer_use_stop` | Emergency stop / resume |
| `computer_history` / `computer_status` | Audit + readiness |

Still available: low-level `desktop_control`, high-level `desktop_*`, optional Zero binary.

## Layers
1. **Browser** — existing Playwright `browser` tool (preferred for web)
2. **Accessibility** — pyatspi when installed
3. **Vision/OCR** — screenshot path for the model + optional tesseract
4. **Input** — ydotool (Wayland) / xdotool (X11) / pyautogui

## Safety tiers
safe / moderate / dangerous (`confirm_dangerous`)

## Install tips
- Wayland input: Repair → Install ydotool
- OCR: `tesseract-ocr`
- Region crop: `Pillow`
- a11y: `python3-pyatspi`
