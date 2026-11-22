# 16 — Connectors، SuperMCP و Godot Proxy

> **وضعیت:** زنده  
> **نسخه سند:** 1.0.0  
> **تاریخ:** 2026-11-22  
> **نسخه محصول مبنا:** 2.0.7+

---

## 1. هدف

توضیح لایهٔ **کانکتورهای MCP بیرونی**، ادغام با **SuperMCP**، و **proxy ابزارهای Godot** داخل رجیستری بومی Dana.

---

## 2. اجزا

| جزء | مسیر کد | نقش |
|------|----------|------|
| Connectors registry | `dana/connectors_registry.py` | ذخیرهٔ `user_connectors.json` در data dir کاربر؛ merge با mcpServers |
| SuperMCP helper | `dana/supermcp.py` | ساخت/به‌روزرسانی config SuperMCP؛ start/stop؛ بدون مسیر شخصی hard-coded |
| Setup API | `dana/setup_service.py` | `/api/setup/connectors`، tools catalog، upsert/remove/import، supermcp/refresh |
| UI Connectors | `ui/src/ConnectorsPage.tsx`, `ui/src/connectors.css` | فرم، JSON import، کاتالوگ ابزار، راهنما FA/EN |
| Godot proxy | `dana/tools/godot_proxy.py` | ثبت ابزارهای `godot_*` در FastMCP Dana؛ forward به SuperMCP |
| Tool registration | `dana/tools/__init__.py`, `dana/tools/tool_catalog.py` | import proxy + دستهٔ `godot` |

---

## 3. جریان داده

```text
Godot Editor (addon / bridge WS :9080)
        ↓
godot-editor-mcp (MCP server)
        ↓
SuperMCP (aggregator, default http://127.0.0.1:3006)
        ↓  (SSE session — یک اتصال زنده؛ موازی نساز)
Dana godot_proxy  →  tools در رجیستری Dana (godot_health_check, …)
        ↓
کلاینت MCP / Control Center
```

**نکته حیاتی:** وجود addon یا فایل config به‌تنهایی اثبات اتصال زنده نیست. برای تأیید باید `tools/call` واقعی (مثلاً health یا project info) موفق شود.

---

## 4. Registry کاربر

- مسیر داده: تحت `XDG_CONFIG_HOME/dana/connectors/` یا `%APPDATA%/dana/connectors/`
- فایل: `user_connectors.json`
- شکل سازگار با Claude Desktop / Cursor `mcpServers`
- نام سرور: `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`

**هرگز** credential یا مسیر ماشین‌خاص را در Git پروژه commit نکن. `.dana/` و تنظیمات local خارج از repository می‌مانند.

---

## 5. متغیرهای محیطی مرتبط

| متغیر | معنی |
|--------|------|
| `DANA_SUPERMCP_URL` | پایهٔ URL SuperMCP (پیش‌فرض `http://127.0.0.1:3006`) |
| `DANA_SUPERMCP_HOME` | مسیر نصب/داده SuperMCP در صورت نیاز |
| envهای خاص کانکتور (مثلاً مسیر باینری Godot) | فقط در registry محلی کاربر |

---

## 6. ابزارهای proxy نمونه (Dana native)

| ابزار Dana | forward تقریبی SuperMCP |
|------------|---------------------------|
| `godot_health_check` | `Godot.godot_health_check` |
| `godot_project_info` | inspection / project info |
| `godot_list_scenes` | list scenes |
| `godot_get_scene_tree` | scene tree |
| `godot_call` | فراخوانی عمومی با نام ابزار remote |
| `godot_list_remote_tools` | enumeration |

پیشوند remote ممکن است `Godot.` باشد؛ proxy باید با کاتالوگ واقعی SuperMCP هم‌تراز بماند.

---

## 7. Setup API (خلاصه)

مسیرها زیر سرویس setup (همراه Control Center):

- لیست / upsert / remove کانکتور
- import JSON
- tools catalog
- refresh config SuperMCP

جزئیات request/response در کد `setup_service.py` مرجع است؛ تغییر قرارداد = به‌روزرسانی این سند + SRS.

---

## 8. عیب‌یابی اتصال زنده Godot

| لایه | بررسی |
|------|--------|
| Godot Editor | پروسه در حال اجرا؛ پروژه باز |
| Bridge | پورت WS (مثلاً 9080) listen |
| godot-editor-mcp | پروسه و tools/list |
| SuperMCP | `DANA_SUPERMCP_URL` در دسترس؛ یک SSE session |
| Dana | `godot_proxy` import؛ tool در list؛ `tools/call` موفق |

اگر هر لایه fail شد، اعلام کن: **LIVE GODOT CONNECTION NOT CONFIRMED** و لایهٔ شکست را بگو.

---

## 9. Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-22 | ثبت معماری connectors + SuperMCP merge + Godot proxy |
