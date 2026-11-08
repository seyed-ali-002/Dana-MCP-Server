# 10 — AI Implementation Guide

> **وضعیت:** زنده (Living Document)  
> **نسخه سند:** 1.0.0  
> **تاریخ:** 2026-11-08  
> **مخاطب:** مدل‌های هوش مصنوعی و توسعه‌دهندگانی که با agent کار می‌کنند  
> **مراجع اجباری قبل از کد:** `09-srs.md` · `08-development-roadmap.md` · `11-ai-guardrails.md` · این فایل

---

## 1. نقش AI در این مخزن

| مجاز | غیرمجاز (بدون تأیید صریح انسان) |
|------|----------------------------------|
| رفع باگ و تکمیل الزامات `Partial`/`Planned` طبق Roadmap | انتشار توکن واقعی، `.env`، یا secret |
| به‌روزرسانی مستندات زنده پس از تغییر رفتار | SemVer major بدون دلیل معماری |
| تست و doctor/smoke محلی | حذف path policy یا `clean_subprocess_env` |
| PR/commit با پیام واضح | بازنویسی کامل UI بدون milestone مربوط |
| افزایش patch/minor هم‌تراز با `06-versioning-release.md` | وابستگی ابری اجباری برای هسته |

**اولویت کار AI:** پایداری اتصال و first-run (Roadmap 1.7) قبل از فیچرهای فان یا UI سنگین.

---

## 2. ترتیب خواندن (Context Pack)

برای هر تسک، به این ترتیب زمینه بگیر:

1. `project_description_md/README.md` — نقشه اسناد  
2. `09-srs.md` — الزام با شناسه (`FR-*` / `UI-*` / `NFR-*`)  
3. `08-development-roadmap.md` — اولویت نسخه و acceptance  
4. `11-ai-guardrails.md` — ممنوعیت‌ها  
5. همین فایل — نگاشت فایل و اسموک  
6. فقط فایل‌های کد مرتبط از جدول بخش 3  

اگر تسک مبهم است: اول شناسه الزام/TECH را مشخص کن؛ بدون شناسه کد ننویس.

---

## 3. نگاشت الزام → فایل (Requirement Traceability)

### 3.1 هسته MCP و runtime

| الزام / موضوع | فایل‌های اصلی |
|----------------|----------------|
| FR-010…016 سرور MCP، worker، tool call | `dana/server.py`, `dana/main.py`, `dana/runtime.py` |
| ثبت ابزارها | `dana/tools/__init__.py`, `dana/tools/tool_catalog.py` |
| orchestration موازی | `dana/tools/runtime_orchestration.py`, `dana/tools/optimization.py` |
| شکل نتیجه MCP / schema | `dana/mcp_result_fix.py` |
| لاگ امن stdio | `dana/file_logging.py` |
| تنظیمات و توکن | `dana/config.py`, `.env.example` |
| HTTP / امنیت transport | `dana/http.py`, `dana/security/http.py` |

### 3.2 نصب، setup، Funnel

| الزام / موضوع | فایل‌های اصلی |
|----------------|----------------|
| FR-001…008 نصب و first-run | `dana/installer.py`, `dana/setup.py`, `dana/cli.py` |
| API برای UI setup | `dana/setup_service.py` |
| Tailscale / Funnel | `dana/tailscale.py`, `dana/public_host.py` |
| SSL / CA | `dana/ssl_util.py` |
| doctor | `dana/doctor.py` |
| deployment / proxy | `dana/deployment.py`, `dana/container.py` |

### 3.3 امنیت و subprocess

| الزام / موضوع | فایل‌های اصلی |
|----------------|----------------|
| Path policy FR-040 | `dana/security/path_policy.py`, `dana/tools/access_policy.py` |
| NFR-002 scrub env | `dana/subprocess_env.py` + همهٔ `subprocess.run/Popen` |
| agent / shell | `dana/tools/agent.py`, `dana/tools/local_agent.py`, `dana/tools/system.py` |

### 3.4 مهارت‌ها، SuperMCP، ابزارها

| موضوع | فایل |
|--------|------|
| Skill registry | `dana/skills_registry.py`, `dana/tools/skills.py` |
| SuperMCP | `dana/supermcp.py` |
| Context / token | `dana/tools/context_engine.py`, `dana/tools/token_analytics.py` |
| Desktop automation | `dana/tools/local_agent.py` |
| Zero computer | `dana/tools/zero_computer.py` |
| Documents | `dana/tools/documents.py`, `dana/tools/formatting.py` |
| Reporting | `dana/reporting.py`, `dana/terminal_ui.py` |

### 3.5 Desktop UI

| الزام | فایل |
|--------|------|
| UI-001…014 Control Center | `ui/src/App.tsx`, `ui/src/App.css` |
| Whip (فان) | `ui/src/WhipOverlay.tsx`, `ui/src/whipAssets.ts`, `ui/public/whip/` |
| لانچر دسکتاپ | `dana/gui.py` |
| Tauri / بیلد | `ui/src-tauri/`, `packaging/*`, `.github/workflows/gui-build.yml` |

### 3.6 نسخه و انتشار

| موضوع | فایل |
|--------|------|
| نسخه Python | `pyproject.toml` |
| همگام‌سازی نسخه | `packaging/set_version.sh` |
| UI version | `ui/package.json`, `ui/src-tauri/tauri.conf.json` |
| سیاست نسخه | `project_description_md/06-versioning-release.md` |

---

## 4. الگوهای اجباری در کد

### 4.1 Subprocess

```python
from dana.subprocess_env import clean_subprocess_env  # یا relative: from .subprocess_env import ...

subprocess.run(cmd, check=False, capture_output=True, text=True, env=clean_subprocess_env())
```

هر `subprocess.run` / `Popen` جدید **بدون** `env=clean_subprocess_env()` یا env معادل scrubشده ممنوع است.

### 4.2 مسیر فایل

```python
from dana.security.path_policy import require_path
path = require_path(user_path, purpose="read")  # یا write
```

دور زدن policy فقط با تصمیم صریح محصولی و به‌روزرسانی SRS.

### 4.3 نتیجه ابزار MCP

- اگر ابزار `outputSchema` ندارد: متن/dict آزاد؛ کلاینت را با schema جعلی نشکن.
- اگر schema ثبت شده: دقیقاً همان ساختار را برگردان.
- خطا: از مسیر failure/`error_result` استفاده کن؛ success با پیام خطا نفرست.
- از `dana.mcp_result_fix` (`ensure_structured`, `error_result`, `strip_tool_output_schemas`) پیروی کن.

### 4.4 لاگ و stdout

- stdout مخصوص پروتکل MCP است.
- لاگ → stderr یا فایل (`file_logging`).
- `print` دیباگ در مسیر سرور ممنوع مگر پشت flag توسعه.

### 4.5 Async

داخل event loop از `asyncio.run` تو در تو استفاده نکن. برای موازی‌سازی: `async def` + `asyncio.gather` (الگوی `runtime_orchestration.py`).

---

## 5. چک‌لیست قبل از اتمام تسک (AI PR Checklist)

```text
[ ] شناسه الزام/TECH/Roadmap مشخص است
[ ] فقط فایل‌های لازم تغییر کرده (diff کوچک‌تر = بهتر)
[ ] هیچ subprocess بدون clean env اضافه نشده
[ ] path policy رعایت شده
[ ] stdout آلوده نشده
[ ] py_compile / تست مرتبط سبز است
[ ] اگر رفتار کاربر عوض شد → 09-srs.md به‌روز شد
[ ] اگر milestone جلو رفت → 08-development-roadmap.md وضعیت آیتم را عوض کرد
[ ] اگر نگاشت فایل عوض شد → این فایل یا 11 به‌روز شد
[ ] توکن/secret در diff نیست
[ ] پیام commit خلاصه و دقیق است
```

---

## 6. اسموک‌تست‌های پیشنهادی

### 6.1 از سورس (Linux/macOS)

```bash
cd /path/to/Dana
python -m py_compile dana/server.py dana/setup.py dana/installer.py
pytest -q || true   # اگر محیط dev آماده است

# در صورت نصب محلی:
dana doctor
dana status        # یا معادل setup.status
```

### 6.2 اتصال

```text
1) dana start / Activate در UI
2) LOCAL endpoint پاسخ دهد (مثلاً health یا MCP initialize)
3) dana stop → نباید خودبه‌خود دوباره start شود
4) در صورت Funnel: PUBLIC جدا از LOCAL گزارش شود
```

### 6.3 رگرسیون subprocess (AppImage/PyInstaller)

```text
از باینری بسته‌بندی‌شده یک ابزار که curl/git صدا می‌زند اجرا شود؛
خطای OPENSSL / unknown url type: https نباید ظاهر شود.
```

### 6.4 UI

```text
باز کردن Control Center → Start/Stop → Logs scroll و collapsible
Quit از tray → پروسه باقی نماند
باز کردن دوباره → یک instance
```

---

## 7. تصمیم‌گیری وقتی کد و SRS اختلاف دارند

1. رفتار **امنیتی** → سخت‌گیرانه‌تر را حفظ کن و SRS را اصلاح کن.  
2. رفتار **کاربرنهایی مستند در README** → با انسان تأیید کن.  
3. باگ واضح در برابر الزام `Must` → الزام غالب است؛ کد را درست کن.  
4. فیچر جدید خارج Roadmap → اول آیتم Roadmap اضافه شود، بعد کد.

---

## 8. همگام‌سازی اسناد زنده

پس از ویرایش `08` / `09` / `10` / `11`:

```bash
bash scripts/sync_living_docs.sh
```

یا دستی کپی به `docs/` طبق اسکریپت.

---

## 9. Changelog

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-08 | ایجاد راهنمای پیاده‌سازی AI با نگاشت فایل و چک‌لیست |
