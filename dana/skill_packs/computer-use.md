---
id: computer-use
name: Computer Use
description: Observe-plan-act-verify desktop/browser control for Dana (Claude-style Computer Use on Linux)
tags: desktop, computer-use, vision, gui
---

# Dana Computer Use

Use this skill for GUI work (video editors, GIMP, native apps) when no API exists.

## Loop
1. `computer_agent_step(goal)` or `computer_observe` — see screen + windows
2. Prefer **browser** tools for web (not screenshots)
3. Prefer **accessibility / window title** before raw coordinates
4. `computer_act(action, …, verify=true)` for mutations
5. On failure: `computer_locate_text` → retry → alternative hotkey
6. `computer_use_stop(true)` emergency halt

## Actions (computer_act)
- Navigation: `open_app`, `focus`, `close`
- Pointer: `click`, `double_click`, `right_click`, `move`, `drag`, `scroll`
- Keyboard: `type`, `type_into`, `key`, `hotkey` / `press_shortcut`
- Sense: `observe`, `locate_text`, `wait`

## Safety
- Dangerous actions need `confirm_dangerous=true` after user approval
- Do not invent sudo/delete without explicit user request

## Wayland
If input fails: Repair → Desktop input, or `desktop_install_input` / `computer_status`
