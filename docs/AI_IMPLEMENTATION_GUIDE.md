# 10 — AI Implementation Guide

> **وضعیت:** زنده (Living Document)  
> **نسخه سند:** 1.0.0  
> **تاریخ:** 2026-11-08  
> **مخاطب:** مدل‌های هوش مصنوعی و توسعه‌دهندگانی که با AI روی Dana کار می‌کنند  
> **وابسته به:** `08-development-roadmap.md`, `09-srs.md`, `11-ai-guardrails.md`

---

## 0. قانون طلایی برای AI

1. **اول بخوان، بعد بنویس:** قبل از تغییر، فایل‌های مرتبط در جدول §3 و guardrailهای `11-ai-guardrails.md` را در نظر بگیر.
2. **کد GitHub/`main` مرجع است** مگر کاربر صریحاً مسیر محلی دیگری بدهد.
3. **بدون معیار پذیرش کار نکن:** هر تسک باید به یک ID از Roadmap (`R17-*`) یا SRS (`FR-*` / `UI-*` / `NFR-*`) وصل شود.
4. **رفتار عمومی عوض شد → SRS + در صورت milestone بودن Roadmap را به‌روز کن.**
5. **توکن واقعی، `.env` واقعی، و secret را commit نکن.**

---

## 1. دامنه اختیارات AI (Decision Boundary)

| مجاز (به‌طور پیش‌فرض) | ممنوع مگر دستور صریح کاربر |
|------------------------|-----------------------------|
| رفع باگ در محدوده تسک | افزایش major version بدون درخواست |
| افزودن تست برای تغییر خود | حذف قابلیت کاربرنهایی |
| به‌روزرسانی docs زنده مرتبط | تغییر LICENSE یا مالکیت |
| refactor محلی محدود | بازنویسی کامل UI/معماری |
| commit/push اگر کاربر خواست | force-push روی `main` |
| تنظیمات نمونه در `.env.example` | نوشتن secret در ریپو |

اگر تسک مبهم است: فرض محافظه‌کارانه بگیر، در پاسخ فرض را بگو، و تغییرات برگشت‌پذیر نگه دار.

---

## 2. ترتیب کار پیشنهادی برای هر تسک

```text
1) تسک را به FR/UI/NFR یا R17/R18/… نگاشت کن
2) جدول §3 → فایل‌های اصلی را باز کن
3) 11-ai-guardrails را برای ضدالگوهای همان حوزه چک کن
4) تغییر حداقلی را اعمال کن
5) py_compile / تست مرتبط / اسموک §5
6) docs زنده در صورت نیاز
7) خلاصه برای انسان: چه عوض شد، چه ریسکی ماند
```

---

## 3. نقشه الزام / حوزه → فایل‌های کد

### 3.1 هسته MCP و runtime

| حوزه / الزام | فایل‌های اصلی |
|--------------|----------------|
| ورود سرور، workers، call_tool wrapper | `dana/server.py` |
| بوت runtime | `dana/runtime.py`, `dana/main.py` |
| تنظیمات و env | `dana/config.py`, `.env.example` |
| شکل نتیجه MCP / schema | `dana/mcp_result_format.py` |
| لاگ امن برای stdio | `dana/file_logging.py` |
| HTTP / امنیت transport | `dana/http.py`, `dana/security/http.py` |
| ثبت ابزارها | `dana/tools/__init__.py` |
| parallel / plan / batch | `dana/tools/runtime_orchestration.py`, `dana/tools/optimization.py` |

### 3.2 نصب، setup، Funnel، endpoint

| حوزه / الزام | فایل‌های اصلی |
|--------------|----------------|
| CLI | `dana/cli.py` |
| Setup state machine / start-stop | `dana/setup.py` |
| Installer / Tailscale install flow | `dana/installer.py` |
| Tailscale API helpers | `dana/tailscale.py` |
| Public host probes | `dana/public_host.py` |
| Setup HTTP API برای UI | `dana/setup_service.py` |
| Doctor | `dana/doctor.py` |
| SSL/CA | `dana/ssl_util.py` |
| Deployment / proxy | `dana/deployment.py` |
| Docker مسیر اختیاری | `dana/container.py` |

### 3.3 امنیت و subprocess

| حوزه / الزام | فایل‌های اصلی |
|--------------|----------------|
| پاک‌سازی env فرزند | `dana/subprocess_env.py` (**اجباری برای هر subprocess خارجی**) |
| Path policy | `dana/security/path_policy.py` |
| Access policy tools | `dana/tools/access_policy.py` |
| Agent filesystem tools | `dana/tools/agent.py` |

### 3.4 ابزارها و skill

| حوزه | فایل |
|------|------|
| Local desktop agent | `dana/tools/local_agent.py` |
| Skills registry | `dana/skills_registry.py`, `dana/tools/skills.py` |
| SuperMCP | `dana/supermcp.py` |
| Context compaction | `dana/tools/context_engine.py` |
| Token analytics | `dana/tools/token_analytics.py` |
| Zero computer | `dana/tools/zero_computer.py` |
| Reporting | `dana/reporting.py` |

### 3.5 Desktop UI

| حوزه | فایل |
|------|------|
| لانچر GUI | `dana/gui.py` |
| اپ React | `ui/src/App.tsx`, `ui/src/App.css` |
| Whip (فان) | `ui/src/WhipOverlay.tsx`, `ui/src/whipAssets.ts`, `ui/public/whip/` |
| Tauri / بیلد | `ui/src-tauri/`, `packaging/*`, `.github/workflows/gui-build.yml` |

### 3.6 نسخه و انتشار

| حوزه | فایل |
|------|------|
| نسخه Python package | `pyproject.toml` |
| ست نسخه | `packaging/set_version.sh` |
| سیاست نسخه | `project_description_md/06-versioning-release.md` |

---

## 4. نگاشت سریع SRS → محل پیاده‌سازی

| ID | خلاصه | محل اولیه |
|----|--------|-----------|
| FR-010…016 | MCP runtime و نتایج | `server.py`, `mcp_result_format.py` |
| FR-018 | session recovery | `server.py`, لایه HTTP MCP |
| FR-003…008 | first-run Tailscale/Funnel | `installer.py`, `setup.py`, UI `App.tsx` |
| FR-020…024 | LOCAL/PUBLIC health | `public_host.py`, `setup.py`, UI |
| FR-030…032 | CLI | `cli.py`, `doctor.py` |
| FR-040…041 | path policy | `security/path_policy.py`, `tools/agent.py` |
| FR-051 | SuperMCP قابل حمل | `supermcp.py` |
| UI-* | Control Center | `ui/src/App.tsx`, `App.css`, `setup_service.py` |
| NFR-002 | env scrub | `subprocess_env.py` + همه callers |
| NFR-005 | CI bundle | `packaging/`, `gui-build.yml` |

---

## 5. اسموک‌تست‌های حداقلی (برای AI پس از تغییر)

### 5.1 همیشه بعد از تغییر Python

```bash
python3 -m py_compile dana/**/*.py  # یا فایل‌های تغییر یافته
# در صورت وجود venv پروژه:
pytest -q --tb=no  # یا حداقل تست‌های مرتبط
```

### 5.2 بعد از تغییر subprocess / agent / installer

```bash
# هیچ subprocess.run/Popen بدون env= نباید بماند (به جز موارد با popen_kwargs/child_env)
rg -n "subprocess\.(run|Popen)\(" dana -g '*.py'
# سپس از نظر منطقی env=clean_subprocess_env را تأیید کن
```

### 5.3 بعد از تغییر MCP result / tools

- ابزار بدون schema → نباید کلاینت را با structured اجباری بشکند.
- خطا → مسیر failure/`error_result` نه success با متن خطا.
- لاگ روی stderr/فایل نه stdout آلوده.

### 5.4 بعد از تغییر setup/UI API

- `dana doctor` (اگر محیط اجازه می‌دهد)
- start → status → stop؛ stop نباید بی‌اجازه دوباره start شود.

### 5.5 بعد از تغییر UI

```bash
cd ui && npm ci && npm run build
```

---

## 6. چک‌لیست PR برای مدل

- [ ] ID الزام/roadmap مشخص شده
- [ ] فقط فایل‌های لازم تغییر کرده
- [ ] guardrailهای مرتبط در `11` رعایت شده
- [ ] `py_compile` / تست مرتبط OK
- [ ] اگر رفتار کاربر عوض شد: `09-srs.md` به‌روز شد
- [ ] اگر milestone جابه‌جا شد: `08-development-roadmap.md` وضعیت آیتم را عوض کرد
- [ ] کپی `docs/` در صورت تغییر 08/09/10/11 هم‌تراز شد (`scripts/sync_living_docs.sh`)
- [ ] راز/توکن commit نشده
- [ ] خلاصه ریسک باقی‌مانده برای انسان نوشته شده

---

## 7. الگوهای کد اجباری (خلاصه)

### 7.1 Subprocess

```python
from dana.subprocess_env import clean_subprocess_env  # یا from .subprocess_env import ...

subprocess.run(cmd, check=False, text=True, capture_output=True, env=clean_subprocess_env())
```

### 7.2 Path

```python
from dana.security.path_policy import require_path
path = require_path(user_path, purpose="read")  # نه Path(x).resolve() خام برای ورودی کاربر
```

### 7.3 نتیجه ابزار

- ترجیح dict/`error_result` واضح
- اگر schema ثبت نشده، structured اجباری برنگردان
- از print روی stdout در مسیر MCP خودداری کن

---

## 8. اسناد مرتبط که AI باید بشناسد

| سند | نقش |
|-----|------|
| `00`–`07` | معماری و دامنه |
| `08` Roadmap | چه چیزی بعدی است |
| `09` SRS | چه چیزی الزام است |
| `10` همین فایل | چطور در کد پیاده شود |
| `11` Guardrails | چه کارهایی ممنوع/خطرناک است |
| `README_FA.md` | پیام کاربرنهایی |

---

## 9. Changelog سند

| نسخه | تاریخ | شرح |
|------|------|------|
| 1.0.0 | 2026-11-08 | ایجاد اولیه برای کار عامل‌های AI روی Dana |
