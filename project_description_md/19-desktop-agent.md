# 19 — Desktop Agent (Wayland / ydotool)

## مشکل رایج Wayland
`desktop_control` روی Linux/Wayland از **ydotool → ydotoold → /dev/uinput** استفاده می‌کند.
اگر `/dev/uinput` قابل نوشتن نباشد و socket مربوط به `ydotoold` در دسترس نباشد، ورودی واقعی کار نمی‌کند.

## راه‌اندازی
1. ابزار MCP: `desktop_setup_input`
2. اسکریپت تولیدشده را با sudo اجرا کنید (مسیر در خروجی ابزار):
   `~/.config/dana/desktop/install-wayland-input.sh`
3. یک‌بار re-login برای گروه `input`
4. دوباره `desktop_setup_input` و سپس `desktop_control(action="diagnostics")`

## لایه‌ها
| لایه | ابزار |
|------|--------|
| Observation | `desktop_observe`, `desktop_control(screenshot)`, `desktop_find_window` |
| Setup | `desktop_setup_input` |
| High-level | `desktop_open_app`, `desktop_focus_app`, `desktop_wait_for`, `desktop_verify`, `desktop_click_element`, `desktop_type_into`, `desktop_press_shortcut`, `desktop_act` |
| Low-level | `desktop_control` (move/click/type/…) |
| Accessibility | `desktop_accessibility` (نیاز به `python3-pyatspi`) |

## الگوی Agent پیشنهادی
`observe → plan → desktop_act/open/focus → verify (+ screenshot) → retry`
